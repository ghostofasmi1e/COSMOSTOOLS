# -*- coding: utf-8 -*-
"""
WD My Cloud OS5 分享链接批量下载器
================================================
命令行用法:
    python mycloud_download.py
        --share "https://os5.mycloud.com/action/share/{shareId}"
        --out D:\\downloads\\关单

图形界面用法:
    python mycloud_gui.py

核心函数(可被 GUI 复用):
    run_download(share_url_or_id, out_dir, log=print) -> (成功数, 失败数)

流程(均来自前端实际调用的官方接口):
   1) GET prod-gateway.wdckeystone.com/shares/v1/shares/{shareId}
      -> 分享内文件/文件夹 id 列表 + 设备 proxyURL + shareToken
   2) 每个 id: GET {device}/sdk/v2/files/{id}  -> 元数据(名称/类型/子项数)
   3) 文件夹: GET {device}/sdk/v1/filesZip?ids={id}&access_token={token}  -> 整个文件夹 zip
      普通文件: GET {device}/sdk/v2/files/{id}/content?download=true&access_token={token}
"""
import argparse
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SHARE_SERVICE = "https://prod-gateway.wdckeystone.com/shares/v1/shares/"

try:
    import certifi  # type: ignore
    ctx = ssl.create_default_context(cafile=certifi.where())
except Exception:  # noqa: BLE001  无 certifi 时退回系统默认证书
    ctx = ssl.create_default_context()
_danger_ctx = ssl._create_unverified_context()
_verify_failed = False
_warn = lambda m: print("[警告] %s" % m)  # noqa: E731


def set_warn(fn):
    global _warn
    _warn = fn


def _open(req, timeout):
    """打开 HTTPS 请求;证书验证失败时降级为不验证(仅一次警告)并重试。"""
    global _verify_failed
    try:
        return urllib.request.urlopen(req, context=ctx, timeout=timeout)
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", None)
        if isinstance(reason, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in str(e):
            if not _verify_failed:
                _verify_failed = True
                _warn("HTTPS 证书验证失败(缺少 CA 证书),已降级为不验证证书继续。"
                      "建议 pip install certifi 恢复完整校验。")
            return urllib.request.urlopen(req, context=_danger_ctx, timeout=timeout)
        raise

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
    "Accept": "application/json, */*",
}


def http(method, url, bearer=None, timeout=120, retries=4):
    hdrs = dict(UA)
    if bearer:
        hdrs["Authorization"] = "Bearer " + bearer
    hdrs["X-Correlation-ID"] = "dshdownloader:%d" % int(time.time() * 1000)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=hdrs, method=method)
            with _open(req, timeout) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e:
            body = e.read()
            if e.code in (429, 500, 502, 503, 504, 408) and attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            return e.code, dict(e.headers), body
        except Exception as e:  # noqa: BLE001
            time.sleep(2 * (attempt + 1))
            if attempt == retries - 1:
                raise RuntimeError("请求失败: %s (%s)" % (url, e))
    raise RuntimeError("请求失败: %s" % url)


def extract_ids(share_url_or_id):
    s = share_url_or_id.strip()
    m = re.search(r"(?:share|shares|folders)/([a-zA-Z0-9\-]{8,64})", s)
    if m:
        return m.group(1)
    if re.fullmatch(r"[a-zA-Z0-9\-]{8,64}", s):
        return s
    raise ValueError("无法识别分享 ID: %r\n请粘贴完整的分享链接(/action/share/...)" % share_url_or_id)


def get_share(share_id, log=print):
    st, _, body = http("GET", SHARE_SERVICE + share_id)
    log("[1] 分享服务 HTTP %s" % st)
    data = json.loads(body.decode("utf-8", "replace")) if body else {}
    if st != 200:
        log(json.dumps(data, ensure_ascii=False)[:400])
        raise RuntimeError("分享服务返回 %s —— 请确认这是分享链接(/action/share/...) 而非个人文件夹地址" % st)
    d = data["data"]
    log("[1] 分享 %s 包含 %d 项, 设备: %s" % (d["shareId"], len(d.get("fileIds") or []), d["device"]["deviceId"]))
    return d


def run_download(share_url_or_id, out_dir, log=print):
    """批量下载分享内容。返回 (成功数, 失败数)。log 为回调,接收文本行。"""
    set_warn(log)
    share_id = extract_ids(share_url_or_id)
    log("[0] 分享 ID: %s" % share_id)
    share = get_share(share_id, log=log)
    base = share["device"]["network"]["proxyURL"]
    if not base.startswith("http"):
        base = "https://" + base
    base = base.rstrip("/")
    token = share["shareToken"]
    log("[2] 设备基址: %s" % base)

    os.makedirs(out_dir, exist_ok=True)
    n_ok = n_fail = 0

    for fid in share.get("fileIds") or []:
        # 元数据:名称/类型
        st, _, body = http("GET", "%s/sdk/v2/files/%s" % (base, fid), bearer=token)
        meta = {}
        if st == 200:
            try:
                meta = json.loads(body.decode("utf-8", "replace"))
            except Exception:
                pass
        name = meta.get("name") or ("item_%s" % fid[:8])
        is_dir = (meta.get("mimeType") == "application/x.wd.dir") or meta.get("childCount") is not None
        log("[3] %s  %s  childCount=%s" % ("[文件夹]" if is_dir else "[文件]", name, meta.get("childCount")))

        safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)[:80]
        if is_dir:
            url = "%s/sdk/v1/filesZip?ids=%s&access_token=%s" % (
                base, urllib.parse.quote(fid), urllib.parse.quote(token))
            save = os.path.join(out_dir, safe + ".zip")
        else:
            url = "%s/sdk/v2/files/%s/content?download=true&access_token=%s" % (
                base, urllib.parse.quote(fid), urllib.parse.quote(token))
            ext = os.path.splitext(name or "")[1] or ".bin"
            save = os.path.join(out_dir, safe + ext)

        st, hdrs, body = http("GET", url, timeout=600)
        if st == 200:
            with open(save, "wb") as f:
                f.write(body)
            log("[4] 已保存 %s  (%d 字节, %s)" % (os.path.basename(save), len(body), hdrs.get("Content-Type", "?")))
            n_ok += 1
        else:
            log("[4] 失败 HTTP %s: %s" % (st, body[:200]))
            n_fail += 1

    log("完成:成功 %d,失败 %d,输出目录 %s" % (n_ok, n_fail, out_dir))
    return n_ok, n_fail


def main(argv=None):
    ap = argparse.ArgumentParser(description="WD My Cloud OS5 分享链接批量下载器")
    ap.add_argument("--share", required=True, help="分享链接或分享 ID")
    ap.add_argument("--out", required=True, help="保存目录")
    args = ap.parse_args(argv)
    ok, fail = run_download(args.share, args.out)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
