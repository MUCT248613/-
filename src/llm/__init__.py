"""
VirtualStudent Sandbox v6.0 - LLM Integration Module

Provides unified access to Aliyun Bailian (DashScope) Qwen models with:
- OpenAI-compatible endpoint
- Cost tracking (llm_calls table)
- Batch processing for identity seeds
- Temperature layering (seed layer high diversity, narrative layer consistency)
- Graceful fallback to deterministic mock when API unavailable

Reference: 技术设计文档 §8.1, §8.7
"""
import json
import os
import time
import uuid
import hashlib
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable

# Preset Aliyun Bailian (百炼) Token Plan OpenAI-compatible endpoint.
# Token Plan (套餐计费) uses a dedicated base URL that differs from the
# pay-as-you-go (按量计费) DashScope endpoint, but the model names are
# identical. This is only a *default* — the actual base_url / model / api_key
# are configured at runtime through the frontend settings page (UI), NOT via
# config files or environment variables.
DEFAULT_BASE_URL = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
# DashScope (Bailian) model ids are case-sensitive and must be LOWERCASE.
# The current-generation models are qwen3.7-flash / qwen3.7-plus / qwen3.7-max;
# qwen-plus / qwen-max / qwen-turbo / qwen-long are older (Qwen 3.0) ids that
# also work. A capitalized id like "Qwen3.7-Plus" is rejected and makes every
# call fail, so always use the lowercase form.
# Default is qwen3.7-flash: persona generation issues many sequential LLM calls
# (identity seed + narrative per student), and flash is several times faster and
# cheaper than plus/max while being more than adequate for this workload.
DEFAULT_MODEL = "qwen3.7-flash"
# Pay-as-you-go (按量计费) DashScope endpoint. A standard Bailian API key
# authenticates here; the Token Plan (套餐) endpoint above only accepts
# subscription-bound keys. test_connection probes this alternative on 401.
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# Local persistence so a backend restart keeps the configured key / endpoint.
# Plain local file (dev tool); never echoed back through the API.
_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "llm_config.json"


def _load_persisted_config() -> Dict[str, Any]:
    if "pytest" in os.sys.modules:  # tests must stay deterministic / offline
        return {}
    try:
        if _CONFIG_PATH.exists():
            return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _persist_config(api_key: str, base_url: str, default_model: str) -> None:
    if "pytest" in os.sys.modules:  # never write side effects during tests
        return
    try:
        _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CONFIG_PATH.write_text(
            json.dumps({"api_key": api_key, "base_url": base_url,
                        "default_model": default_model}, ensure_ascii=False),
            encoding="utf-8")
    except Exception:
        pass


class LLMClient:
    """
    Unified LLM client for Qwen models via DashScope OpenAI-compatible endpoint.
    
    Falls back to a deterministic mock when no API key is configured, so the
    full pipeline remains runnable offline (critical for testing/demo).
    """
    
    # Cost table (yuan per 1K tokens) - Qwen pricing approximation
    PRICING = {
        "qwen-plus": {"input": 0.0008, "output": 0.002},
        "qwen-max": {"input": 0.02, "output": 0.06},
        "qwen-turbo": {"input": 0.0003, "output": 0.0006},
    }
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None,
                 default_model: str = DEFAULT_MODEL, cost_tracker: Optional[Callable] = None):
        # Configuration is UI-driven: no environment-variable / file fallback.
        # An empty api_key means "not configured yet" -> deterministic offline mode.
        self.api_key = api_key or ""
        self.base_url = base_url or DEFAULT_BASE_URL
        self.default_model = default_model
        self.cost_tracker = cost_tracker  # callback(call_record: dict)
        self._client = None
        self.last_error: Optional[str] = None
        
        if self.api_key:
            try:
                from openai import OpenAI
                # Bound each request so a stalled network / DashScope call cannot
                # hang run creation indefinitely (the OpenAI default is 600s).
                # On timeout the call() wrapper degrades to the deterministic mock.
                self._client = OpenAI(api_key=self.api_key, base_url=self.base_url,
                                      timeout=30.0)
            except ImportError:
                self._client = None
    
    @property
    def is_live(self) -> bool:
        """Whether a real LLM backend is available"""
        return self._client is not None
    
    def call(self, prompt: str, model: Optional[str] = None,
             temperature: float = 0.7, max_tokens: int = 2000,
             response_format: Optional[Dict] = None,
             system_prompt: str = "", strict: bool = False) -> str:
        """
        Single LLM call with cost tracking and deterministic fallback.
        
        Args:
            prompt: User prompt
            model: Model name (default: the configured default_model)
            temperature: Sampling temperature (seed layer 0.9-1.1, narrative 0.7)
            max_tokens: Max completion tokens
            response_format: e.g. {"type": "json_object"}
            system_prompt: Optional system message
        
        Returns:
            Completion text (or deterministic mock output when offline)
        """
        model = model or self.default_model
        
        if self.is_live:
            try:
                self.last_error = None
                return self._call_live(prompt, model, temperature, max_tokens,
                                       response_format, system_prompt)
            except Exception as e:
                self.last_error = f"{type(e).__name__}: {e}"
                if strict:
                    raise
                # Graceful degradation: a transient LLM failure (rate limit,
                # network hiccup, invalid model id) must not abort the whole
                # simulation run. Fall back to the deterministic mock and log
                # loudly so the degradation is visible, never silent.
                print(f"[LLM] live call failed ({type(e).__name__}: {e}); "
                      f"falling back to deterministic mock", flush=True)
                return self._call_mock(prompt, model, temperature)
        return self._call_mock(prompt, model, temperature)
    
    def _call_live(self, prompt, model, temperature, max_tokens,
                   response_format, system_prompt) -> str:
        """Real API call via OpenAI-compatible client"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format
        
        t0 = time.time()
        response = self._client.chat.completions.create(**kwargs)
        latency_ms = int((time.time() - t0) * 1000)
        
        text = response.choices[0].message.content
        usage = response.usage
        
        self._record_call(
            model=model,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            latency_ms=latency_ms,
        )
        return text
    
    def _call_mock(self, prompt: str, model: str, temperature: float) -> str:
        """
        Deterministic mock output when no API key.
        Generates stable, varied output derived from prompt hash so that
        batch generation still produces unique personas offline.
        """
        # Simulate token counts for cost accounting
        prompt_tokens = max(1, len(prompt) // 2)
        completion_tokens = 120
        
        self._record_call(
            model=f"{model}-mock",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=0,
        )
        
        # Return a marker so callers know this is mock output.
        # Callers that need structured JSON should use call_json() which
        # provides a proper deterministic structure.
        return f"[MOCK_LLM:{hashlib.md5(prompt.encode()).hexdigest()[:8]}]"
    
    def call_json(self, prompt: str, model: Optional[str] = None,
                  temperature: float = 0.7, fallback: Optional[Any] = None) -> Any:
        """
        Call LLM expecting JSON output. Parses result; returns fallback on failure.
        """
        raw = self.call(prompt, model=model, temperature=temperature,
                        response_format={"type": "json_object"})
        try:
            # Strip markdown fences if present
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
            return json.loads(cleaned)
        except (json.JSONDecodeError, IndexError):
            return fallback if fallback is not None else {}
    
    def generate_identity_seeds_batch(self, skeleton_constraints: str,
                                      batch_size: int = 8,
                                      temperature: float = 1.0) -> List[Dict]:
        """
        Batch-generate identity seeds (L2 layer). One call produces batch_size
        seeds, reducing API calls ~10x. Reference: §8.7
        
        Args:
            skeleton_constraints: Text description of parameter skeleton constraints
            batch_size: Number of seeds per call (5-10 recommended)
            temperature: High diversity for seed layer (0.9-1.1)
        
        Returns:
            List of identity seed dicts
        """
        prompt = (
            f"基于以下参数骨架，生成 {batch_size} 个虚拟学生的身份种子（JSON 数组）：\n"
            f"{skeleton_constraints}\n\n"
            f"每个身份种子包含：name（独特姓名，避免套路名）、birth_place（具体到区县）、"
            f"family_structure_type、core_personality_seed、"
            f"unique_life_seed（一个影响学习态度的独特早期经历，要有细节）。\n\n"
            f"要求：\n"
            f"1. {batch_size} 个个体之间必须显著不同（姓名/背景/经历无重复主题）\n"
            f"2. 避免常见人设套路，包含至少 1 个长尾特征\n"
            f"3. 输出纯 JSON 数组"
        )
        
        if self.is_live:
            result = self.call_json(prompt, temperature=temperature, fallback=[])
            if isinstance(result, dict) and "seeds" in result:
                result = result["seeds"]
            return result if isinstance(result, list) else []
        
        # Offline: deterministic unique seeds
        return self._mock_seeds(skeleton_constraints, batch_size)
    
    def _mock_seeds(self, constraints: str, batch_size: int) -> List[Dict]:
        """Deterministic offline identity seed generation"""
        surnames = ["张", "李", "王", "刘", "陈", "杨", "赵", "黄", "周", "吴",
                    "徐", "孙", "胡", "朱", "高", "林", "何", "郭", "马", "罗"]
        givens = ["明宇", "思远", "雨桐", "浩然", "欣怡", "子涵", "梓轩", "诗琪",
                  "宇航", "梦瑶", "博文", "雅静", "天翊", "语嫣", "俊杰", "晓彤"]
        cities = ["浙江省金华市武义县", "江苏省南京市江宁区", "广东省深圳市宝安区",
                  "四川省成都市郫都区", "湖北省武汉市黄陂区", "山东省青岛市即墨区"]
        structures = ["完整家庭", "单亲家庭", "留守家庭", "重组家庭"]
        personalities = ["内向但执着，擅长独立思考", "外向开朗，行动力强",
                         "敏感细腻，富有同理心", "沉稳踏实，目标明确"]
        
        base = hashlib.md5(constraints.encode()).hexdigest()
        seeds = []
        for i in range(batch_size):
            h = int(hashlib.md5(f"{base}-{i}".encode()).hexdigest()[:8], 16)
            seeds.append({
                "name": surnames[h % len(surnames)] + givens[(h // 7) % len(givens)],
                "birth_place": cities[h % len(cities)],
                "family_structure_type": structures[h % len(structures)],
                "core_personality_seed": personalities[h % len(personalities)],
                "unique_life_seed": f"早期经历#{h % 97}：一次独特的生活事件塑造了其学习态度。",
            })
        return seeds
    
    def _record_call(self, model: str, prompt_tokens: int,
                     completion_tokens: int, latency_ms: int):
        """Record call for cost accounting"""
        pricing = self.PRICING.get(model.replace("-mock", ""),
                                   {"input": 0.001, "output": 0.002})
        cost = (prompt_tokens / 1000 * pricing["input"] +
                completion_tokens / 1000 * pricing["output"])
        
        record = {
            "call_id": str(uuid.uuid4()),
            "module": "llm",
            "model": model,
            "live": not model.endswith("-mock"),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_yuan": round(cost, 6),
            "latency_ms": latency_ms,
            "timestamp_ms": int(time.time() * 1000),
        }
        
        _call_log.append(record)
        if len(_call_log) > 100:
            del _call_log[: len(_call_log) - 100]

        if self.cost_tracker:
            try:
                self.cost_tracker(record)
            except Exception:
                pass

    def test_connection(self) -> Dict[str, Any]:
        """Actually call the configured endpoint once (minimal prompt) and
        report success / the exact error, so connectivity is verifiable."""
        if not self.is_live:
            return {"status": "offline",
                    "reason": "未配置 API Key 或缺少 openai 依赖，当前为确定性离线模式"}
        t0 = time.time()
        try:
            resp = self._client.chat.completions.create(
                model=self.default_model,
                messages=[{"role": "user", "content": "请只回复一个词：ok"}],
                temperature=0.0, max_tokens=8,
            )
            return {"status": "ok", "model": self.default_model,
                    "latency_ms": int((time.time() - t0) * 1000),
                    "reply": (resp.choices[0].message.content or "").strip()[:50]}
        except Exception as e:
            result = {"status": "error", "model": self.default_model,
                      "latency_ms": int((time.time() - t0) * 1000),
                      "reason": f"{type(e).__name__}: {e}"}
            if "invalid_api_key" in str(e) or "401" in str(e):
                # Key/endpoint mismatch is the most common 401: probe the
                # pay-as-you-go endpoint with the same key and suggest it.
                if self.base_url.rstrip("/") != DASHSCOPE_BASE_URL.rstrip("/"):
                    try:
                        from openai import OpenAI
                        alt = OpenAI(api_key=self.api_key, base_url=DASHSCOPE_BASE_URL,
                                     timeout=30)
                        alt.chat.completions.create(
                            model=self.default_model,
                            messages=[{"role": "user", "content": "请只回复一个词：ok"}],
                            max_tokens=5)
                        result["suggestion"] = (
                            "该 Key 被当前端点拒绝，但在按量计费端点验证可用："
                            f"请将 Base URL 改为 {DASHSCOPE_BASE_URL} 后保存。")
                    except Exception:
                        pass
            return result


# Module-level singleton for convenience
_default_client: Optional[LLMClient] = None

# Recent call records (live + mock) so usage is visible in the UI / logs
_call_log: List[Dict[str, Any]] = []


def get_call_log() -> List[Dict[str, Any]]:
    return list(_call_log)


def get_client() -> LLMClient:
    """Get or create the default LLM client (restores persisted config)."""
    global _default_client
    if _default_client is None:
        saved = _load_persisted_config()
        _default_client = LLMClient(
            api_key=saved.get("api_key") or None,
            base_url=saved.get("base_url") or None,
            default_model=saved.get("default_model") or DEFAULT_MODEL,
        )
    return _default_client


def reconfigure_client(api_key: Optional[str] = None,
                       base_url: Optional[str] = None,
                       default_model: Optional[str] = None) -> LLMClient:
    """
    Reconfigure the module-level singleton at runtime (e.g. from the
    frontend settings page). Pass None for any field to keep its current value.
    Returns the (re)configured client.
    """
    global _default_client
    prev = _default_client
    new_key = api_key if api_key is not None else (prev.api_key if prev else None)
    new_url = base_url if base_url is not None else (prev.base_url if prev else None)
    new_model = default_model if default_model is not None else (
        prev.default_model if prev else DEFAULT_MODEL)
    _default_client = LLMClient(api_key=new_key, base_url=new_url,
                                default_model=new_model)
    _persist_config(_default_client.api_key, _default_client.base_url,
                    _default_client.default_model)
    return _default_client


def get_config() -> Dict[str, Any]:
    """Return the current LLM configuration (API key masked)."""
    client = get_client()
    masked = ""
    if client.api_key:
        k = client.api_key
        masked = k[:4] + "****" + k[-4:] if len(k) > 8 else "****"
    return {
        "base_url": client.base_url,
        "default_model": client.default_model,
        "api_key_set": bool(client.api_key),
        "api_key_masked": masked,
        "is_live": client.is_live,
    }


def call_qwen(prompt: str, model: Optional[str] = None, temperature: float = 0.7,
              **kwargs) -> str:
    """Convenience wrapper matching the documented call_qwen() interface (§8.6).
    model=None uses the currently configured default_model (set via the UI)."""
    return get_client().call(prompt, model=model, temperature=temperature, **kwargs)
