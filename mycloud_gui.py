# -*- coding: utf-8 -*-
"""
WD My Cloud OS5 分享链接下载器 - 图形界面版(多链接排队)
=========================================================
用法: python mycloud_gui.py

操作:粘贴分享链接(可多个,每行一个)→ 选择保存目录 → 点「开始下载」。
多个链接按顺序排队下载,完成一个再下一个;下载过程实时显示日志。
"""
import os
import re
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from mycloud_download import extract_ids, run_download  # noqa: E402


def parse_links(text):
    """从多行文本解析链接列表:每行一个,去掉空行;按分享 ID 去重(完整链接/裸 ID 视为同一个)。"""
    seen, out = set(), []
    for raw in text.replace(",", "\n").splitlines():
        s = raw.strip()
        if not s:
            continue
        try:
            sid = extract_ids(s)
        except ValueError:
            sid = None
        key = sid or s
        if key in seen:
            continue
        seen.add(key)
        out.append(sid or s)
    return out


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("WD 云盘分享链接下载器(多链接排队)")
        self.geometry("840x640")
        self.minsize(680, 520)
        self.busy = False

        pad = {"padx": 8, "pady": 5}

        frm = ttk.LabelFrame(self, text="1. 填写与选择")
        frm.pack(fill="x", padx=10, pady=8)

        ttk.Label(frm, text="分享链接:").grid(row=0, column=0, sticky="nw", **pad)
        self.txt_links = tk.Text(frm, height=5, wrap="none")
        self.txt_links.grid(row=0, column=1, sticky="we", **pad)
        sb = ttk.Scrollbar(frm, orient="vertical", command=self.txt_links.yview)
        sb.grid(row=0, column=2, sticky="ns")
        self.txt_links.configure(yscrollcommand=sb.set)
        self.txt_links.focus_set()

        ttk.Label(frm, text="保存目录:").grid(row=1, column=0, sticky="w", **pad)
        self.var_out = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_out).grid(row=1, column=1, sticky="we", **pad)
        ttk.Button(frm, text="浏览…", command=self._pick_out).grid(row=1, column=2, **pad)

        frm.columnconfigure(1, weight=1)

        ttk.Label(
            frm,
            text="提示:每行一个分享链接(可多行),多个链接将按顺序排队依次下载。\n"
            "链接形如 https://os5.mycloud.com/action/share/xxxx,在云盘网页里对文件夹右键 → 分享 → 复制查看链接",
            foreground="#666",
        ).grid(row=2, column=0, columnspan=3, sticky="w", padx=8, pady=(2, 6))

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=10, pady=4)
        self.btn_start = ttk.Button(btns, text="开始下载", command=self._start)
        self.btn_start.pack(side="left", padx=6)
        self.btn_open = ttk.Button(btns, text="打开目录", command=self._open_dir, state="disabled")
        self.btn_open.pack(side="left", padx=6)
        self.status = ttk.Label(btns, text="", foreground="#888")
        self.status.pack(side="left", padx=12)

        ttk.LabelFrame(self, text="下载日志").pack(fill="both", expand=True, padx=10, pady=6)
        self.log = scrolledtext.ScrolledText(self, height=16, state="disabled")
        self.log.pack(fill="both", expand=True, padx=18, pady=(0, 10))

    # ------------------------------------------------------------------
    def _pick_out(self):
        d = filedialog.askdirectory(title="选择保存目录")
        if d:
            self.var_out.set(d)
            self._set_openable(d)

    def _set_openable(self, d):
        self.btn_open.configure(state="normal" if os.path.isdir(d) else "disabled")

    def _open_dir(self):
        d = self.var_out.get().strip()
        if not os.path.isdir(d):
            return
        if sys.platform == "darwin":
            import subprocess
            subprocess.run(["open", d])
        elif os.name == "nt":
            os.startfile(d)  # noqa: S606
        else:
            import subprocess
            subprocess.run(["xdg-open", d])

    def _log(self, msg):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _short(self, link):
        m = re.search(r"/([a-zA-Z0-9\-]{8,64})$", link.strip())
        return m.group(1) if m else link.strip()[:40]

    def _start(self):
        if self.busy:
            return
        links = parse_links(self.txt_links.get("1.0", "end"))
        out = self.var_out.get().strip()
        if not links:
            messagebox.showwarning("提示", "请先粘贴分享链接(每行一个)")
            return
        if not out:
            messagebox.showwarning("提示", "请选择保存目录")
            return
        if not os.path.isdir(out):
            try:
                os.makedirs(out, exist_ok=True)
            except OSError as e:
                messagebox.showerror("错误", "无法创建目录:\n%s" % e)
                return
        self.busy = True
        self.btn_start.configure(state="disabled")
        self.status.configure(text="下载中…")
        self._log("=" * 60)
        self._log("共 %d 个链接,开始排队下载…" % len(links))
        threading.Thread(target=self._worker, args=(links, out), daemon=True).start()

    def _worker(self, links, out):
        total_ok = total_fail = 0
        fails = []
        for i, link in enumerate(links, 1):
            self.after(0, self._log, "----- 链接 %d/%d: %s -----" % (i, len(links), self._short(link)))
            try:
                ok, fail = run_download(link, out, log=lambda m: self.after(0, self._log, m))
                total_ok += ok
                total_fail += fail
                if fail:
                    fails.append(self._short(link))
            except Exception as e:  # noqa: BLE001
                self.after(0, self._log, "[错误] 链接 %s: %s" % (self._short(link), e))
                total_fail += 1
                fails.append(self._short(link))
        self.after(0, self._done, total_ok, total_fail, fails, out)

    def _done(self, ok, fail, fails, out):
        self._log("全部结束。成功 %d 项,失败 %d 项。" % (ok, fail))
        if fails:
            self._log("失败链接: " + ", ".join(fails))
        self.busy = False
        self.btn_start.configure(state="normal")
        self.status.configure(text="空闲")
        self._set_openable(out)
        if fail == 0:
            messagebox.showinfo("完成", "全部下载成功,共 %d 项!\n已保存到:\n%s" % (ok, out))
        else:
            messagebox.showwarning("完成", "成功 %d 项,失败 %d 项,详见日志" % (ok, fail))


if __name__ == "__main__":
    App().mainloop()
