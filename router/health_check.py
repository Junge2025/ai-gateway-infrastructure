"""军鸽云链 - 3分钟健康检测器"""
import os, json, time, ssl, logging
import urllib.request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("health_check")

CHECK_INTERVAL = 180  # 3分钟
FAILURE_THRESHOLD = 2
RECOVERY_INTERVAL = 300
TIMEOUT = 10

NODES = [
    {"name": "ollama_local",  "url": "http://localhost:11434/api/tags"},
    {"name": "github_models", "url": "http://154.36.179.107:8080/health"},
    {"name": "gemini_flash",  "url": "http://154.36.179.107:8080/health"},
    {"name": "deepseek",      "url": "https://api.deepseek.com/v1/models"},
    {"name": "openrouter",    "url": "https://openrouter.ai/api/v1/models"},
    {"name": "apiporter",     "url": "https://www.apiporter.com/v1/models"},
    {"name": "openai",        "url": "https://api.openai.com/v1/models"},
]

def check_node(node):
    try:
        start = time.time()
        req = urllib.request.Request(node["url"])
        resp = urllib.request.urlopen(req, timeout=TIMEOUT, context=ssl.create_default_context())
        latency = int((time.time() - start) * 1000)
        return {"status": "up", "latency_ms": latency, "http_code": resp.status}
    except Exception as e:
        return {"status": "down", "error": str(e)[:100]}

def load_matrix():
    try:
        with open("health/health_matrix.json") as f:
            return json.load(f)
    except:
        return {}

def save_matrix(matrix):
    os.makedirs("health", exist_ok=True)
    with open("health/health_matrix.json", "w") as f:
        json.dump(matrix, f, indent=2)

def main():
    logger.info("Health check cycle start")
    matrix = load_matrix()
    
    for node in NODES:
        name = node["name"]
        prev = matrix.get(name, {"status": "unknown", "failures": 0})
        result = check_node(node)
        
        entry = {
            "status": result["status"],
            "latency_ms": result.get("latency_ms", 0),
            "last_check": time.time(),
            "failures": prev.get("failures", 0) + (1 if result["status"] == "down" else 0),
            "rate_limited": result.get("http_code") == 429,
        }
        
        if result["status"] == "down":
            entry["failures"] = prev.get("failures", 0) + 1
            if entry["failures"] >= FAILURE_THRESHOLD:
                entry["status"] = "down_confirmed"
                logger.warning(f"CONFIRMED DOWN: {name} ({entry['failures']} failures)")
        else:
            entry["failures"] = 0
            logger.info(f"UP: {name} ({result['latency_ms']}ms)")
        
        matrix[name] = entry
    
    save_matrix(matrix)
    logger.info("Health check cycle complete")

if __name__ == "__main__":
    main()
