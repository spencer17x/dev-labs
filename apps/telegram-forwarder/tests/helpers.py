from types import SimpleNamespace


class FakeMessage:
    def __init__(
        self,
        text=None,
        sender_id=None,
        sender_username=None,
        media=None,
        photo=None,
        video=None,
        document=None,
        audio=None,
        sticker=None,
        voice=None,
        is_reply=False,
        sender_is_bot=False,
        post=False,
        message_id=101,
        chat_id=202,
    ):
        self.text = text
        self.sender_id = sender_id
        self.sender = SimpleNamespace(username=sender_username, bot=sender_is_bot)
        if sender_username is None and not sender_is_bot:
            self.sender = None
        self.media = media
        self.photo = photo
        self.video = video
        self.document = document
        self.audio = audio
        self.sticker = sticker
        self.voice = voice
        self.id = message_id
        self.chat_id = chat_id
        self.is_reply = is_reply
        self.reply_to_msg_id = 1 if is_reply else None
        self.post = post
