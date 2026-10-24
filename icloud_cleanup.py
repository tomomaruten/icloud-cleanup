"""
iCloudメール 自動完全削除スクリプト
指定した文字列が 件名・差出人・本文 のどこかに含まれるメールを完全削除する。
受信箱・迷惑メール・ゴミ箱が対象。GitHub Actions で定期実行する想定。
"""
import email
import imaplib
import os
from datetime import date, timedelta
from email.header import decode_header, make_header

KEYWORDS = ["ジュエルライブ事務局", "マダムライブ事務局"]
FOLDERS = ["INBOX", "Junk", "Deleted Messages"]
DAYS = 3  # 直近何日分をチェックするか

USER = os.environ["ICLOUD_USER"]
PASSWORD = os.environ["ICLOUD_APP_PASSWORD"]  # App用パスワード（Apple IDのパスワードではない）
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"


def dec(s):
    try:
        return str(make_header(decode_header(s or "")))
    except Exception:
        return s or ""


def text_of(msg):
    parts = [dec(msg.get("Subject")), dec(msg.get("From"))]
    for part in msg.walk():
        if part.get_content_maintype() != "text":
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        charset = part.get_content_charset() or "utf-8"
        try:
            parts.append(payload.decode(charset, errors="ignore"))
        except LookupError:
            parts.append(payload.decode("utf-8", errors="ignore"))
    return "\n".join(parts)


def main():
    since = (date.today() - timedelta(days=DAYS)).strftime("%d-%b-%Y")
    imap = imaplib.IMAP4_SSL("imap.mail.me.com", 993)
    imap.login(USER, PASSWORD)

    for folder in FOLDERS:
        typ, _ = imap.select(f'"{folder}"')
        if typ != "OK":
            print(f"[skip] {folder} を開けませんでした")
            continue

        _, data = imap.uid("search", None, "SINCE", since)
        hits = []
        for uid in data[0].split():
            _, fetched = imap.uid("fetch", uid, "(BODY.PEEK[])")  # PEEKなので既読にならない
            raw = next((x[1] for x in fetched if isinstance(x, tuple)), None)
            if raw is None:
                continue
            msg = email.message_from_bytes(raw)
            if any(k in text_of(msg) for k in KEYWORDS):
                hits.append(uid)
                print(f"[{folder}] 該当: {dec(msg.get('Subject'))}")

        if hits and not DRY_RUN:
            imap.uid("store", b",".join(hits), "+FLAGS", "(\\Deleted)")
            imap.expunge()
            print(f"[{folder}] {len(hits)}件を完全削除")
        elif hits:
            print(f"[DRY RUN][{folder}] {len(hits)}件が対象（削除はしていません）")

    imap.logout()


if __name__ == "__main__":
    main()
