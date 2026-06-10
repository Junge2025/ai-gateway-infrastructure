"""军鸽云链 AI 网关 - 多模型智能路由器 Phase 1"""
import os, time, json, logging
from flask import Flask, request, jsonify
from functools import wraps

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("model_router")

# ═══ 优先级链 (从 YAML 加载，fallback 用内置) ═══
DEFAULT_CHAIN = [
    {"name": "ollama_local",  "url": "http://host.docker.internal:11434/v1", "cost": 0,    "timeout": 30},
    {"name": "github_models", "url": "http://154.36.179.107:8080/v1/github", "cost": 0,    "timeout": 20},
    {"name": "gemini_flash",  "url": "http://154.36.179.107:8080/v1/gemini", "cost": 0,    "timeout": 15},
    {"name": "deepseek",      "url": "https://api.deepseek.com/v1",          "cost": 0.001,"timeout": 10},
    {"name": "openrouter",    "url": "https://openrouter.ai/api/v1",         "cost": 0.002,"timeout": 15},
    {"name": "apiporter",     "url": "https://www.apiporter.com/v1",         "cost": 0.005,"timeout": 15},
    {"name": "openai",        "url": "https://api.openai.com/v1",            "cost": 0.01, "timeout": 15},
]

HEALTH_MATRIX = {}
COST_BUDGET = float(os.getenv("MONTHLY_BUDGET", "300"))  # ¥300/月

def load_health_matrix():
    """加载健康矩阵"""
    try:
        with open("health/health_matrix.json") as f:
            return json.load(f)
    except:
        return {}

def get_available_model(chain=None):
    """按优先级链获取第一个可用模型"""
    if chain is None:
        chain = DEFAULT_CHAIN
    matrix = load_health_matrix()
    
    for node in chain:
        name = node["name"]
        status = matrix.get(name, {}).get("status", "unknown")
        rate_limited = matrix.get(name, {}).get("rate_limited", False)
        latency = matrix.get(name, {}).get("latency_ms", 9999)
        
        if status == "down":
            logger.warning(f"SKIP {name}: DOWN")
            continue
        if rate_limited:
            logger.warning(f"SKIP {name}: RATE_LIMITED")
            continue
        if latency > 2000:
            logger.warning(f"SKIP {name}: HIGH_LATENCY ({latency}ms)")
            continue
        
        logger.info(f"SELECT {name} (cost={node['cost']}, latency={latency}ms)")
        return node
    
    logger.error("ALL MODELS UNAVAILABLE")
    return None

def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get("X-API-Key", "")
        if not key:
            return jsonify({"error": "Missing X-API-Key header"}), 401
        return f(*args, **kwargs)
    return decorated

@app.route("/health")
def health():
    return jsonify({"status": "ok", "timestamp": time.time()})

@app.route("/v1/models", methods=["GET"])
@require_api_key
def list_models():
    matrix = load_health_matrix()
    available = []
    for node in DEFAULT_CHAIN:
        n = node["name"]
        s = matrix.get(n, {})
        available.append({
            "id": n, "cost": node["cost"],
            "status": s.get("status", "unknown"),
            "latency_ms": s.get("latency_ms", 0),
        })
    return jsonify({"object": "list", "data": available})

@app.route("/v1/chat/completions", methods=["POST"])
@require_api_key
def chat_completions():
    data = request.get_json()
    chain_name = request.headers.get("X-Chain", "default")
    
    model = get_available_model()
    if not model:
        return jsonify({"error": "All models unavailable"}), 503
    
    # 转发请求到选中的模型
    import urllib.request as urlreq
    target_url = model["url"] + "/chat/completions"
    
    # 注入 API key
    api_key = os.getenv(f'{model["name"].upper()}_API_KEY', '')
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    req = urlreq.Request(target_url, data=json.dumps(data).encode(), headers=headers, method="POST")
    try:
        resp = urlreq.urlopen(req, timeout=model["timeout"], context=ssl.create_default_context())
        return jsonify(json.loads(resp.read()))
    except Exception as e:
        logger.error(f"Model {model['name']} failed: {e}")
        return jsonify({"error": f"Model unavailable: {str(e)}"}), 502

@app.route("/stats")
@require_api_key
def stats():
    return jsonify({
        "budget_monthly": COST_BUDGET,
        "health": load_health_matrix(),
        "uptime": time.time(),
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081)
