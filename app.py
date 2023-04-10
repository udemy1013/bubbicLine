from flask import Flask, request, abort
import requests, os
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, ImageMessage, ImageSendMessage, FollowEvent, UnfollowEvent
from PIL import Image
from io import BytesIO
import psycopg2


LINE_CHANNEL_ACCESS_TOKEN = "KrsoYg1GiMN7MAOdMH26a3bvi2NU63nnk0jkO+n95M2OQf8/ckcpSPD0Oydu4MSjCqOtu46loEspRbq6ryUV3ojJg9SGFhRzVTttFGY9E6QJ+37UklrOAOOb/lJ4pARC5uSAww0fqW9lQ85mTu1NmgdB04t89/1O/w1cDnyilFU="
LINE_CHANNEL_SECRET = "8713e9bb416010b8da56acb7c6c26e70"
DATABASE_URL = "~~~~~あなたのデータベースURL~~~~~" 

app = Flask(__name__)

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

header = {
    "Content_Type": "application/json",
    "Authorization": "Bearer " + LINE_CHANNEL_ACCESS_TOKEN
}

@app.route("/")
def hello_world():
    return "hello world!"


# アプリにPOSTがあったときの処理
@app.route("/callback", methods=["POST"])
def callback():
    # get X-Line-Signature header value
    signature = request.headers["X-Line-Signature"]
    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"


# botにメッセージを送ったときの処理
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=event.message.text))
    print("返信完了!!\ntext:", event.message.text)


# botに画像を送ったときの処理
@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    print("画像を受信")
    message_id = event.message.id
    image_path = getImageLine(message_id)
    line_bot_api.reply_message(
        event.reply_token,
        ImageSendMessage(
            original_content_url = Heroku + image_path["main"],
            preview_image_url = Heroku + image_path["preview"]
        )
    )
    print("画像の送信完了!!")


# 受信メッセージに添付された画像ファイルを取得
def getImageLine(id):
    line_url = f"https://api-data.line.me/v2/bot/message/{id}/content"
    result = requests.get(line_url, headers=header)
    print(result)

    img = Image.open(BytesIO(result.content))
    w, h = img.size
    if w >= h:
        ratio_main, ratio_preview = w / 1024, w / 240
    else:
        ratio_main, ratio_preview = h / 1024, h / 240

    width_main, width_preview = int(w // ratio_main), int(w // ratio_preview)
    height_main, height_preview = int(h // ratio_main), int(h // ratio_preview)

    img_main = img.resize((width_main, height_main))
    img_preview = img.resize((width_preview, height_preview))
    image_path = {
        "main": f"static/images/image_{id}_main.jpg",
        "preview": f"static/images/image_{id}_preview.jpg"
    }
    img_main.save(image_path["main"])
    img_preview.save(image_path["preview"])
    return image_path


# データベース接続
def get_connection():
    return psycopg2.connect(DATABASE_URL, sslmode="require")


# botがフォローされたときの処理
@handler.add(FollowEvent)
def handle_follow(event):
    profile = line_bot_api.get_profile(event.source.user_id)
    with get_connection() as conn:
        with conn.cursor() as cur:
            conn.autocommit = True
            cur.execute('CREATE TABLE IF NOT EXISTS users(user_id TEXT)')
            cur.execute('INSERT INTO users (user_id) VALUES (%s)', [profile.user_id])
            print('userIdの挿入OK!!')
            cur.execute('SELECT * FROM users')
            db = cur.fetchall()
    print("< データベース一覧 >")
    for db_check in db:
        print(db_check)


# botがアンフォロー(ブロック)されたときの処理
@handler.add(UnfollowEvent)
def handle_unfollow(event):
    with get_connection() as conn:
        with conn.cursor() as cur:
            conn.autocommit = True
            cur.execute('DELETE FROM users WHERE user_id = %s', [event.source.user_id])
    print("userIdの削除OK!!")


# データベースに登録されたLINEアカウントからランダムでひとりにプッシュ通知
def push():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM users ORDER BY random() LIMIT 1')
            (to_user,) = cur.fetchone()
    line_bot_api.multicast([to_user], TextSendMessage(text="今日もお疲れさん!!"))


# アプリの起動
if __name__ == "__main__":
    # 初回のみデータベースのテーブル作成
    with get_connection() as conn:
        with conn.cursor() as cur:
            conn.autocommit = True
            cur.execute('CREATE TABLE IF NOT EXISTS users(user_id TEXT)')
    
    # LINE botをフォローしているアカウントのうちランダムで一人にプッシュ通知
    push()
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
### End