from typing import Annotated, AsyncGenerator, Literal
import httpx
import ormsgpack
from pydantic import AfterValidator, BaseModel, conint

class ServeReferenceAudio(BaseModel):
    audio: bytes
    text: str

class ServeTTSRequest(BaseModel):
    text: str
    reference_id: str = "57eab548c7ed4ddc974c4c153cb015b2"  # 使用 reference_id 替代 voice_id
    chunk_length: Annotated[int, conint(ge=100, le=300, strict=True)] = 200
    format: Literal["wav", "pcm", "mp3"] = "mp3"
    mp3_bitrate: Literal[64, 128, 192] = 128
    normalize: bool = True
    latency: Literal["normal", "balanced"] = "normal"

def test_fish_tts():
    # 测试文本 - 使用一段出版新闻
    test_text = """据中国新闻出版广电报报道，2024年全国图书零售市场呈现稳步复苏态势。实体书店客流量持续回升，线上图书销售额同比增长15%。童书、文学、社科等品类表现突出，其中儿童科普读物和原创文学作品增长最为显著。业内专家指出，这反映出读者的阅读需求正在向多元化、高质量方向发展。"""
    
    request = ServeTTSRequest(
        text=test_text,
        reference_id="57eab548c7ed4ddc974c4c153cb015b2",  # 使用 reference_id
        mp3_bitrate=192,
        normalize=True,
        latency="normal"
    )

    with (
        httpx.Client() as client,
        open("test_fish_output.mp3", "wb") as f,
    ):
        with client.stream(
            "POST",
            "https://api.fish.audio/v1/tts",
            content=ormsgpack.packb(request, option=ormsgpack.OPT_SERIALIZE_PYDANTIC),
            headers={
                "authorization": "Bearer f773e309617b4c96ae747a379438de0c",  # 使用你的 API key
                "content-type": "application/msgpack",
            },
            timeout=None,
        ) as response:
            for chunk in response.iter_bytes():
                f.write(chunk)
            print("✅ 音频文件已保存为: test_fish_output.mp3")

if __name__ == "__main__":
    test_fish_tts() 