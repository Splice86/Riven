"""Web crawler module using lynx."""

import subprocess
from modules import Module


def fetch_page(url: str) -> str:
    """Fetch a web page using lynx and return text content.
    
    Args:
        url: The URL to fetch
        
    Returns:
        Text content of the page
    """
    if not url.startswith(('http://', 'https://')):
        return f"Error: URL must start with http:// or https://"
    
    try:
        result = subprocess.run(
            ['lynx', '-dump', '-nolist', '-width=200', url],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            return f"Error fetching {url}: {result.stderr}"
        
        content = result.stdout.strip()
        if not content:
            return f"Error: No content found at {url}"
        
        # Truncate very long pages
        if len(content) > 10000:
            content = content[:10000] + f"\n\n... (truncated, {len(content)} total chars)"
        
        return content
    
    except subprocess.TimeoutExpired:
        return f"Error: Timeout fetching {url}"
    except Exception as e:
        return f"Error: {e}"


def fetch_page_links(url: str) -> str:
    """Fetch a web page and return just the links.
    
    Args:
        url: The URL to fetch
        
    Returns:
        List of links from the page
    """
    if not url.startswith(('http://', 'https://')):
        return f"Error: URL must start with http:// or https://"
    
    try:
        result = subprocess.run(
            ['lynx', '-dump', '-nolist', url],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            return f"Error fetching {url}: {result.stderr}"
        
        # Extract links (lines starting with numbers followed by URL)
        lines = result.stdout.strip().split('\n')
        links = []
        for line in lines:
            # Links in lynx dump are typically in format: "  1. http://..."
            if line.strip().startswith(('http://', 'https://')):
                links.append(line.strip())
        
        if not links:
            return f"No links found at {url}"
        
        return "Links found:\n" + "\n".join(f"  - {link}" for link in links[:50])
    
    except subprocess.TimeoutExpired:
        return f"Error: Timeout fetching {url}"
    except Exception as e:
        return f"Error: {e}"


def web_search(query: str, num_results: int = 10) -> str:
    """Search the web using DuckDuckGo lite.
    
    Args:
        query: Search query
        num_results: Number of results to return (default: 10)
        
    Returns:
        Search results with titles and URLs
    """
    import re
    try:
        # Use DuckDuckGo HTML version
        url = f"https://lite.duckduckgo.com/lite/?q={query.replace(' ', '+')}"
        result = subprocess.run(
            ['lynx', '-dump', '-nolist', '-width=200', url],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            return f"Error searching: {result.stderr}"
        
        lines = result.stdout.strip().split('\n')
        results = []
        
        # Parse results: numbered entries followed by description, then URL
        current_result = None
        
        for line in lines:
            line = line.strip()
            
            # Skip header and navigation
            if not line:
                continue
            if 'DuckDuckGo' in line or 'Next Page' in line:
                continue
            if line.startswith('__'):
                continue
            
            # Match numbered results: "1. Title" or "  1. Title"
            match = re.match(r'^\s*(\d+)\.\s+(.+)$', line)
            if match:
                if current_result and current_result not in results:
                    results.append(current_result)
                # Start new result
                title = match.group(2).strip()
                current_result = title
                continue
            
            # If we have a current result, append description lines
            if current_result:
                # URL lines (start with http)
                if line.startswith(('http://', 'https://')):
                    current_result += f" | {line}"
                    if current_result not in results:
                        results.append(current_result)
                    current_result = None
                # Description lines
                elif len(line) > 10 and 'duckduckgo' not in line.lower():
                    current_result += f" - {line}"
            
            if len(results) >= num_results:
                break
        
        # Add last result if not added
        if current_result and current_result not in results:
            results.append(current_result)
        
        if not results:
            return f"No results found for: {query}"
        
        output = [f"Search results for: {query}", ""]
        for i, r in enumerate(results, 1):
            output.append(f"{i}. {r}")
        
        return '\n'.join(output)
    
    except subprocess.TimeoutExpired:
        return "Error: Search timeout"
    except Exception as e:
        return f"Error: {e}"


def get_module() -> Module:
    """Create the web module."""
    return Module(
        name="web",
        enrollment=lambda: None,
        functions={
            "fetch_page": fetch_page,
            "fetch_page_links": fetch_page_links,
            "web_search": web_search,
        }
    )