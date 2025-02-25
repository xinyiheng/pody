import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time
import json
import edge_tts
import asyncio
import os
from typing import List, Dict
import shutil

class PodcastGenerator:
    def __init__(self):
        self.rss_url = "https://www.inoreader.com/stream/user/1005507650/tag/%E5%9B%BD%E5%86%85%E5%87%BA%E7%89%88%E5%95%86%E5%85%AC%E4%BC%97%E5%8F%B7"
        # 从环境变量获取 API key
        self.api_key = os.environ.get('API_KEY')
        if not self.api_key:
            raise ValueError("API_KEY environment variable is not set")
        self.api_base = "https://openrouter.ai/api/v1/chat/completions"
        self.cache_file = "article_cache.json"
        self.progress_file = "process_progress.json"
        self.web_dir = 'web'
        self.public_dir = os.path.join(self.web_dir, 'public')
        self.podcasts_dir = os.path.join(self.public_dir, 'podcasts')
        self.index_file = os.path.join(self.web_dir, 'podcast_index.json')
        
        # 确保必要的目录存在
        for directory in [self.web_dir, self.public_dir, self.podcasts_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)

    def load_cache(self) -> Dict:
        """加载文章缓存，并清理过期内容"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                    
                # 清理7天前的缓存
                current_time = datetime.now()
                cleaned_cache = {'articles': {}}
                
                for url, article_data in cache['articles'].items():
                    try:
                        article_time = datetime.strptime(article_data['timestamp'], '%Y-%m-%d %H:%M:%S')
                        if (current_time - article_time).days < 7:
                            cleaned_cache['articles'][url] = article_data
                    except:
                        continue
                
                return cleaned_cache
            return {'articles': {}}
        except Exception as e:
            print(f"加载缓存失败: {e}")
            return {'articles': {}}

    def save_cache(self, cache: Dict):
        """保存文章缓存"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存缓存失败: {e}")

    def update_podcast_index(self, podcast_data: Dict) -> None:
        """更新播客索引文件"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.index_file), exist_ok=True)
            
            if os.path.exists(self.index_file):
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    index = json.load(f)
                    print(f"当前索引包含 {len(index['podcasts'])} 个播客")
                    print(f"索引文件位置: {self.index_file}")
            else:
                index = {"podcasts": []}
                print(f"创建新的索引文件: {self.index_file}")
            
            # 将新播客添加到列表开头
            index["podcasts"].insert(0, podcast_data)
            print(f"添加新播客: {podcast_data['id']}")
            print(f"音频文件路径: {os.path.join(self.podcasts_dir, podcast_data['id'], 'podcast.mp3')}")
            
            # 保存更新后的索引
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(index, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 索引文件已更新: {self.index_file}")
            print(f"现在索引包含 {len(index['podcasts'])} 个播客")
            
        except Exception as e:
            print(f"更新索引文件失败: {e}")
            import traceback
            print(traceback.format_exc())

    async def generate_broadcast_script(self, summaries: List[Dict]) -> str:
        """生成单人播报稿"""
        try:
            valid_summaries = [s for s in summaries if s.get('summary') and s['summary'].strip()]
            
            if not valid_summaries:
                print("没有有效的文章内容可以讨论")
                return ""
            
            article_count = len(valid_summaries)
            input_text = "\n\n".join([
                f"文章{i+1}:\n标题: {s['title']}\n来源: {s['source']}\n总结:\n{s['summary']}"
                for i, s in enumerate(valid_summaries)
            ])
            
            prompt = f"""你是一位专业的播客内容创作者，擅长将多篇文章整合成自然流畅的单人口播稿件。请根据以下{article_count}篇文章，生成一期出版行业新闻播报。

内容材料（共{article_count}篇文章）：
{input_text}

具体要求：

1. 内容组织
   - 按主题（如文学、童书、商业、数字出版等）对文章进行分类整理
   - 相似主题的内容放在一起讨论，使用自然的过渡句连接
   - 每个主题下的内容要突出重点，展现深度

2. 来源引用
   - 每篇文章必须准确提及其真实来源
   - 来源引用要自然融入语句，避免生硬堆砌

3. 语言风格
   - 保持专业性和权威感，同时语言要生动易懂
   - 使用广播新闻的语气和节奏
   - 避免过于口语化的表达

4. 结构要求
   - 不要添加开场白和结束语
   - 每篇文章讨论篇幅300字左右
   - 确保覆盖所有文章的核心内容
   - 突出行业影响和深层分析

请直接输出播报内容，以广播新闻的专业风格呈现。"""

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "https://github.com/",
                "Content-Type": "application/json"
            }

            payload = {
                "model": "qwen/qwen-turbo",
                "messages": [
                    {
                        "role": "system",
                        "content": "你是出版电台的专业主播，擅长制作新闻播报内容。"
                    },
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "top_p": 0.9
            }

            response = requests.post(
                self.api_base,
                headers=headers,
                json=payload,
                timeout=180  # 进一步增加超时时间到3分钟
            )
            
            response.raise_for_status()
            script = response.json()["choices"][0]["message"]["content"]
            
            # 验证是否包含所有文章
            for summary in valid_summaries:
                if summary['source'] not in script:
                    print(f"警告：未找到来源 '{summary['source']}' 的内容")
            
            # 保存文稿
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            podcast_dir = os.path.join(self.podcasts_dir, timestamp)
            if not os.path.exists(podcast_dir):
                os.makedirs(podcast_dir)
            
            script_file = os.path.join(podcast_dir, 'script.txt')
            with open(script_file, 'w', encoding='utf-8') as f:
                f.write(script)
            
            print(f"\n播报稿已生成并保存到: {script_file}")
            return script
            
        except requests.exceptions.RequestException as e:
            print(f"API 请求失败: {str(e)}")
            if hasattr(e.response, 'text'):
                print(f"错误详情: {e.response.text}")
            return ""

    async def generate_audio(self, text: str, timestamp: str) -> str:
        """使用Edge TTS生成音频"""
        print("开始生成音频...")
        try:
            # 确保目录存在
            podcast_dir = os.path.join(self.podcasts_dir, timestamp)
            if not os.path.exists(podcast_dir):
                os.makedirs(podcast_dir)
            
            communicate = edge_tts.Communicate(
                text, 
                "zh-CN-XiaoxiaoNeural",
                rate="+50%"
            )
            
            audio_file = os.path.join(podcast_dir, 'podcast.mp3')
            await communicate.save(audio_file)
            
            print(f"✅ 音频文件已保存到: {audio_file}")
            return audio_file
        except Exception as e:
            print(f"生成音频失败: {e}")
            return None

    def fetch_article_content(self, url, max_retries=3):
        """获取文章全文内容，支持重试"""
        print(f"\n正在处理URL: {url}")
        
        for attempt in range(max_retries):
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    'Connection': 'keep-alive'
                }
                
                if 'mp.weixin.qq.com' in url:
                    response = requests.get(url, headers=headers, timeout=30)
                    response.encoding = 'utf-8'
                    
                    soup = BeautifulSoup(response.text, 'html.parser')
                    article = soup.find('div', id='js_content')
                    
                    if article:
                        # 清理文章内容
                        for tag in article.find_all(True):
                            if 'style' in tag.attrs:
                                del tag.attrs['style']
                        
                        for unwanted in article.find_all(['script', 'style', 'iframe']):
                            unwanted.decompose()
                        
                        # 获取文本段落
                        paragraphs = []
                        seen_texts = set()
                        
                        for element in article.find_all(['p', 'section', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                            text = ' '.join(element.get_text(strip=True).split())
                            
                            if (text and 
                                len(text) > 2 and
                                not any(text.startswith(x) for x in [
                                    '微信', '图片', '●', '©', '=', '...', '「', '校对', 
                                    '编辑', '复审', '终审', '推荐', '阅读', '点击', '关注',
                                    '来源', '作者', '标题', '发布时间', '原文链接', '内容'
                                ]) and
                                not any(x in text for x in [
                                    '扫描二维码', '长按图片', '点击上方', '关注我们', 
                                    '新媒体矩阵', '原创文章', '欢迎转发', '朋友圈'
                                ])):
                                
                                is_substring = False
                                for seen_text in seen_texts:
                                    if text in seen_text or seen_text in text:
                                        is_substring = True
                                        break
                                
                                if not is_substring and text not in seen_texts:
                                    seen_texts.add(text)
                                    paragraphs.append(text)
                        
                        content = '\n\n'.join(paragraphs)
                        
                        if len(content) > 100:
                            print(f"成功获取文章内容，长度: {len(content)} 字符")
                            return content
                        
                        if attempt < max_retries - 1:
                            print(f"内容太短，尝试重新获取 (尝试 {attempt + 2}/{max_retries})")
                            time.sleep(3)  # 等待几秒后重试
                            continue
                    
                    if attempt < max_retries - 1:
                        print(f"未找到文章内容，尝试重新获取 (尝试 {attempt + 2}/{max_retries})")
                        time.sleep(3)
                        continue
                    else:
                        print("多次尝试后仍未获取到有效内容")
                        return "无法获取文章内容"
                    
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"获取失败，尝试重新获取 (尝试 {attempt + 2}/{max_retries}): {e}")
                    time.sleep(3)
                    continue
                else:
                    print(f"多次尝试后获取失败: {e}")
                    return f"获取文章内容失败: {str(e)}"
        
        return "无法获取文章内容"

    def fetch_rss_articles(self, num_pages=5):
        """获取RSS文章列表，支持多页获取和去重"""
        try:
            print("开始获取RSS文章...")
            
            articles = []
            cache = self.load_cache()
            
            # 获取已处理的URL和它们的时间戳
            processed_urls = {}
            for url, data in cache['articles'].items():
                try:
                    timestamp = datetime.strptime(data['timestamp'], '%Y-%m-%d %H:%M:%S')
                    processed_urls[url] = timestamp
                except:
                    continue
            
            seen_urls = set()
            
            for page in range(num_pages):
                page_url = f"{self.rss_url}?n=20&p={page + 1}"
                print(f"\n获取第 {page + 1} 页...")
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'application/rss+xml,application/xml;q=0.9,*/*;q=0.8'
                }
                
                response = requests.get(page_url, headers=headers, timeout=30)
                feed = feedparser.parse(response.text)
                
                if not feed.entries:
                    print(f"第 {page + 1} 页没有更多文章")
                    break
                    
                print(f"找到 {len(feed.entries)} 篇文章")
                
                for entry in feed.entries:
                    try:
                        # 检查是否在当前运行中已处理
                        if entry.link in seen_urls:
                            continue
                        
                        # 检查是否在缓存中且未过期
                        if entry.link in processed_urls:
                            cache_time = processed_urls[entry.link]
                            if (datetime.now() - cache_time).days < 7:
                                print(f"跳过最近处理的文章: {entry.get('title', 'No title')}")
                                continue
                        
                        seen_urls.add(entry.link)
                        
                        print(f"\n处理文章: {entry.get('title', 'No title')}")
                        
                        author = entry.get('dc_creator', '未知作者')
                        source = entry.get('source', {}).get('title', '未知来源')
                        
                        content = self.fetch_article_content(entry.link)
                        if content and content != "无法获取文章内容":
                            article = {
                                'title': entry.title,
                                'author': author,
                                'source': source,
                                'link': entry.link,
                                'pub_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'content': content
                            }
                            articles.append(article)
                            
                            # 更新缓存
                            cache['articles'][entry.link] = {
                                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'data': article
                            }
                            
                            print(f"成功添加文章: {entry.title}")
                            
                            if len(articles) >= 100:  # 限制最大文章数
                                print("\n已达到最大文章数限制(100)")
                                break
                        
                        time.sleep(2)  # 避免频繁请求
                        
                    except Exception as e:
                        print(f"处理文章时出错: {e}")
                        continue
                
                if len(articles) >= 100:
                    break
                
                time.sleep(3)  # 页面之间添加延迟
            
            # 保存更新后的缓存
            self.save_cache(cache)
            
            print(f"\n成功获取 {len(articles)} 篇新文章")
            return articles
            
        except Exception as e:
            print(f"获取RSS文章失败: {e}")
            import traceback
            print(traceback.format_exc())
            return []

    def summarize_with_ai(self, articles: List[Dict]) -> List[Dict]:
        summaries = []
        for article in articles:
            try:
                print(f"\n正在总结文章: {article['title']}")
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                # 打印请求信息（注意隐藏完整 API key）
                print(f"API Key 前缀: {self.api_key[:10]}...")
                print(f"请求 URL: {self.api_base}")
                
                response = requests.post(
                    self.api_base,
                    headers=headers,
                    json={
                        "model": "anthropic/claude-3-opus-20240229",
                        "messages": [
                            {"role": "user", "content": f"请将这篇文章总结为适合播客的内容，语气要自然流畅，要包含文章的主要观点和有趣的细节。\n\n文章标题：{article['title']}\n\n作者：{article['author']}\n\n内容：{article['content']}"}
                        ]
                    },
                    timeout=60
                )
                
                # 打印响应状态和内容
                print(f"响应状态码: {response.status_code}")
                if response.status_code != 200:
                    print(f"错误响应: {response.text}")
                
                response.raise_for_status()
                summary = {
                    'title': article['title'],
                    'author': article['author'],
                    'source': article['source'],
                    'summary': response.json()["choices"][0]["message"]["content"]
                }
                summaries.append(summary)
                
                # 避免频繁请求
                time.sleep(2)
            except Exception as e:
                print(f"AI总结失败: {str(e)}")
                continue
        
        return summaries

async def main():
    generator = PodcastGenerator()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 1. 获取文章
    articles = generator.fetch_rss_articles()
    if not articles:
        print("未获取到文章")
        return
    
    print(f"\n成功获取 {len(articles)} 篇文章:")
    for i, article in enumerate(articles, 1):
        print(f"{i}. {article['title']} ({len(article['content'])} 字)")
    
    # 2. AI总结
    summaries = generator.summarize_with_ai(articles)
    if not summaries:
        print("AI总结失败")
        return
    
    # 3. 生成播报稿
    script = await generator.generate_broadcast_script(summaries)
    if not script:
        print("生成播报稿失败")
        return
    
    # 确保使用同一个时间戳创建目录
    podcast_dir = os.path.join(generator.podcasts_dir, timestamp)
    if not os.path.exists(podcast_dir):
        os.makedirs(podcast_dir)
    
    # 保存文稿
    script_file = os.path.join(podcast_dir, 'script.txt')
    with open(script_file, 'w', encoding='utf-8') as f:
        f.write(script)
    
    # 4. 生成音频 - 传入相同的时间戳
    audio_file = await generator.generate_audio(script, timestamp)
    
    # 更新索引文件 - 使用相同的时间戳
    podcast_data = {
        'id': timestamp,
        'date': datetime.now().strftime('%Y-%m-%d'),
        'title': f"出版电台播报 {datetime.now().strftime('%Y年%m月%d日')}",
        'summary': summaries[0]['title'] if summaries else "",
        'audio_path': f'/podcasts/{timestamp}/podcast.mp3',
        'script_path': f'/podcasts/{timestamp}/script.txt'
    }
    generator.update_podcast_index(podcast_data)
    
    # 添加文件检查
    script_file = os.path.join(podcast_dir, 'script.txt')
    audio_file = os.path.join(podcast_dir, 'podcast.mp3')
    index_file = generator.index_file
    
    print("\n文件检查:")
    print(f"播客目录: {os.path.exists(podcast_dir)}")
    print(f"文稿文件: {os.path.exists(script_file)}")
    print(f"音频文件: {os.path.exists(audio_file)}")
    print(f"索引文件: {os.path.exists(index_file)}")
    
    # 打印目录内容
    if os.path.exists(generator.web_dir):
        print("\n网站目录内容:")
        for root, dirs, files in os.walk(generator.web_dir):
            print(f"\n{root}:")
            for d in dirs:
                print(f"  📁 {d}")
            for f in files:
                print(f"  📄 {f}")
    
    print("\n处理完成!")
    print(f"文件已保存在: {os.path.join(generator.podcasts_dir, timestamp)}")

if __name__ == "__main__":
    asyncio.run(main()) 