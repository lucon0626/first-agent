"""
搜索工具 — 使用 DuckDuckGo 搜索互联网信息。

特点：
- 免费，不需要 API Key
- 返回摘要和相关话题
- 适合查找新闻、事实、人物介绍等
"""
import requests


def web_search(query: str, max_results: int = 3) -> str:
    """
    用 DuckDuckGo 搜索互联网。

    参数:
        query: 搜索关键词
        max_results: 最多返回几条相关话题（默认 3）

    返回:
        搜索结果的文本摘要，或提示信息
    """
    url = "https://api.duckduckgo.com/"
    params = {
        "q": query,
        "format": "json",
        "no_html": "1",          # 去除 HTML 标签
        "skip_disambig": "1",    # 跳过消歧义页面
    }

    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()

        results = []

        # 提取摘要（如果有的话）
        if data.get("AbstractText"):
            results.append(f"摘要：{data['AbstractText']}")

        # 提取相关话题
        for topic in data.get("RelatedTopics", [])[:max_results]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append(f"- {topic['Text']}")

        return "\n".join(results) if results else f"没有找到关于「{query}」的结果"

    except requests.Timeout:
        return "搜索超时，请稍后重试或换个关键词"
    except requests.RequestException as e:
        return f"搜索网络错误：{e}"
    except Exception as e:
        return f"搜索出错：{e}"
