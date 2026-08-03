"""
Student Generator - Complete 4-Layer Pipeline
L1 → L2 → L3 → L4 → Final Student Archive with Uniqueness Guarantee

Reference: 档案设计文档 §1.4
"""
from typing import Dict, List, Tuple, Optional, Callable
from dataclasses import asdict
import json
import time
from datetime import datetime, timedelta

from . import UniquenessGuarantor
from .identity_seed import (
    IdentitySeedGenerator, Layer1SkeletonGenerator, IdentitySeed
)
from .layers_3_4 import Layer3DerivationEngine, Layer4CoherenceEngine
from ..llm import get_client


def _strip_json_fences(text: str) -> str:
    """Strip markdown code fences that LLMs sometimes wrap JSON output in."""
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        if len(parts) >= 2:
            cleaned = parts[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
    return cleaned.strip()


class StudentGenerator:
    """
    Complete student generation pipeline
    
    四层管线：
    L1: 随机骨架采样 (deterministic, from posterior)
    L2: LLM 身份种子 (creative, high temp)
    L3: 规则派生 + LLM 叙事 (hybrid)
    L4: 指纹校验去重 (deterministic)
    """
    
    def __init__(self, posterior_dist: Dict = None, llm_func: Callable = None):
        """
        Args:
            posterior_dist: Calibrated BKT posterior distribution
            llm_func: Function to call LLM (mock-able for testing). When None,
                      defaults to the real Qwen (千问) client via Aliyun Bailian
                      (DashScope); if no API key has been configured in the
                      frontend settings page (UI) it transparently falls back to
                      a deterministic offline mock so demos and the test suite
                      remain runnable.
        """
        self.posterior_dist = posterior_dist or {
            "p_know": {"mu": 0.3, "sigma": 0.15},
            "p_learn": {"mu": 0.25, "sigma": 0.08}
        }
        self.llm_func = llm_func or self._default_llm
        # Whether a custom llm_func was injected (e.g. by tests). The batched
        # cohort path only runs against the real client, never an injected func.
        self._custom_llm = llm_func is not None
        self.uniqueness_guarantor = UniquenessGuarantor()
        # Cohort-level name registry. The identity fingerprint (L4) hashes
        # several fields, so two students can share a *name* yet pass the
        # fingerprint check -- a visible violation of the v5.0 "every
        # individual is unique" promise (FR-A10). Tracking names here lets
        # generate_student() retry until each name is unique within a cohort.
        self._used_names = set()
        # Monotonic counter backing _force_unique_name()'s deterministic
        # collision resolution (see that method).
        self._name_fallback_counter = 0

    def _default_llm(self, prompt: str, temperature: float = 0.9,
                     max_tokens: int = 2000) -> str:
        """Route persona generation to the real Qwen model when available.

        - When an API key has been configured via the frontend settings page
          (UI): calls Aliyun Bailian Qwen, so the L2 identity-seed and L3
          narrative layers are genuinely LLM-generated
          (C1 比赛硬性：基于国产开源大模型)。
        - Otherwise: falls back to the deterministic offline mock so the full
          pipeline still runs without network access.

        ``max_tokens`` is forwarded to the live client so batched calls (which
        return several personas per response) can request a larger completion.
        """
        client = get_client()
        if client.is_live:
            raw = client.call(prompt, temperature=temperature, max_tokens=max_tokens)
            return _strip_json_fences(raw)
        return self._mock_llm(prompt, temperature)

    def _mock_llm(self, prompt: str, temperature: float = 0.9) -> str:
        """Mock LLM for testing (returns unique dummy JSON per prompt).

        Diversity matters: the offline fallback must still honour the v5.0
        uniqueness promise (FR-A10), so every field is derived from
        independent slices of the prompt hash rather than held constant (the
        old version returned the SAME family structure / personality / life
        seed for every student). A larger name pool plus the cohort-level
        retry in generate_student() keeps names collision-free.
        """
        import hashlib
        digest = hashlib.md5(prompt.encode()).hexdigest()
        h = int(digest[:8], 16)
        h2 = int(digest[8:16], 16)
        surnames = ["张", "李", "王", "刘", "陈", "杨", "赵", "黄", "周", "吴",
                    "徐", "孙", "胡", "朱", "高", "林", "何", "郭", "马", "罗",
                    "梁", "宋", "郑", "谢", "韩", "唐", "冯", "于", "董", "萧"]
        # Gendered given-name pools so a name always matches the student's
        # gender (avoid feminine names for boys / masculine names for girls).
        # Gender is derived from the same prompt hash as the name, so the two
        # can never disagree and the output stays reproducible per seed.
        male_given = ["明宇", "浩然", "梓轩", "宇航", "博文", "天翊", "俊杰",
                      "文博", "昊天", "志强", "烨磊", "鹏涛", "熠彤", "鸿煊",
                      "炎彬", "越彬", "鑫鹏", "黎昕", "旭尧", "伟宸", "擎宇",
                      "楷瑞", "致远", "明辉", "砚舟", "睿泽"]
        female_given = ["雨桐", "欣怡", "诗琪", "梦瑶", "雅静", "语嫣", "晓彤",
                        "紫萱", "思颖", "若曦", "静怡", "婉婷", "瑾萱", "靖瑶",
                        "梦洁", "雅琳", "惠茜", "曼玉", "歆瑶", "凌薇", "碧萱",
                        "钰彤", "馨彤", "若彤", "嘉懿", "晨曦"]
        gender = "男" if (h & 1) == 0 else "女"
        given_pool = male_given if gender == "男" else female_given
        # Independent hash slices for surname / given name spread collisions.
        name = surnames[h % len(surnames)] + given_pool[h2 % len(given_pool)]
        cities = ["浙江省金华市", "江苏省南京市", "广东省深圳市", "四川省成都市",
                  "湖北省武汉市", "山东省青岛市", "福建省厦门市", "湖南省长沙市",
                  "安徽省合肥市", "河南省郑州市", "陕西省西安市", "辽宁省沈阳市"]
        family_structures = ["完整家庭", "核心家庭", "单亲家庭", "隔代抚养",
                             "重组家庭", "留守家庭"]
        personality_seeds = [
            "内向但执着，擅长独立思考",
            "外向活泼，善于团队协作",
            "敏感细腻，对评价十分在意",
            "好胜心强，遇强则强",
            "温和随性，兴趣驱动学习",
            "谨慎慢热，需要稳定预期",
        ]
        life_seeds = [
            "八岁时因一次数学竞赛获奖，产生了对理科的热情，成为学习的主要驱动力。",
            "小学时一位老师的当众表扬让其建立了自信，从此敢于在课堂上发言。",
            "曾因转学难以融入新集体，那段经历让其格外看重同伴关系。",
            "家里经营小生意，耳濡目染下养成了精打细算、目标明确的习惯。",
            "一次生病休学后成绩下滑，重新追赶的过程磨炼了抗挫能力。",
            "祖辈是乡村教师，从小在书堆里长大，阅读面广但偏科明显。",
        ]
        return json.dumps({
            "name": name,
            "gender": gender,
            "birth_place": cities[h % len(cities)],
            "family_structure_type": family_structures[(h >> 4) % len(family_structures)],
            "core_personality_seed": personality_seeds[(h2 >> 3) % len(personality_seeds)],
            "unique_life_seed": life_seeds[(h >> 8) % len(life_seeds)],
        })
    
    # Given-name character pool used by _force_unique_name() to deterministically
    # resolve a name collision without depending on LLM cooperation.
    _GIVEN_NAME_POOL = (
        "砚舟楒然瑶瑾萱睿泽宇轩涵怡悦宁致远明辉晨曦若彤"
        "嘉懿静怡烨磊婉婷鹏涛熠彤靖瑶鸿煊梦洁炎彬雅琳越彬"
    )

    def _force_unique_name(self, name: str) -> str:
        """Return ``name`` if unused, else a deterministically-mutated unique variant.

        The L2 retry loop asks the LLM to avoid already-used names, but a strong
        model can still converge on the same name for near-identical skeletons
        (the L1 prompt varies very little across students). This is the final,
        LLM-independent guarantee behind the v5.0 uniqueness promise (FR-A10):
        keep the surname and draw given-name characters from a pool, advancing a
        counter until the combination is unused. In offline mock mode collisions
        do not occur, so this is a no-op there and reproducibility is preserved.
        """
        if name and name not in self._used_names:
            return name
        surname = name[:1] if name else "学"
        pool = self._GIVEN_NAME_POOL
        n = len(pool)
        for _ in range(n * n):
            idx = self._name_fallback_counter
            self._name_fallback_counter += 1
            candidate = surname + pool[idx % n] + pool[(idx // n) % n]
            if candidate not in self._used_names:
                return candidate
        # Extremely defensive: unreachable for realistic cohort sizes.
        self._name_fallback_counter += 1
        return f"{surname}某{self._name_fallback_counter}"

    def generate_student(self, student_id: str, seed: int = None,
                         preset_identity_seed: Optional[IdentitySeed] = None,
                         preset_narrative: Optional[Dict] = None) -> Tuple[Dict, str]:
        """
        Generate a single student through 4-layer pipeline
        
        Args:
            student_id: Unique ID for this student
            seed: Random seed for reproducibility
            
        Returns:
            (student_archive_dict, status_message)
        """
        import numpy as np
        if seed is not None:
            np.random.seed(seed)
        
        # Layer 1: Sample skeleton from posterior
        skeleton = Layer1SkeletonGenerator.sample_skeleton(self.posterior_dist)
        
        # Layer 2: LLM generate identity seed.
        # Retry until the generated name is unique within this generator's
        # cohort. The L1 skeleton (calibrated cognitive params) stays fixed
        # across attempts -- only the creative identity layer varies -- so
        # same-seed runs remain fully reproducible.
        #
        # In LIVE mode the L1 prompt varies very little across students (most
        # skeleton fields are constant), so a strong model keeps converging on
        # the same name. We therefore (a) hand the model the explicit list of
        # already-used names to avoid, and (b) on retries ask it plainly to
        # switch to a different name. The prompt enhancement is live-only so
        # the offline mock (which hashes the prompt) stays byte-for-byte
        # reproducible. Either way, _force_unique_name() below is the final
        # LLM-independent guarantee (FR-A10).
        if preset_identity_seed is not None:
            # Batched cohort path: identity seed already generated + uniquified.
            identity_seed = preset_identity_seed
        else:
            identity_seed = self._generate_identity_seed(skeleton)
            if identity_seed is None:
                return None, "llm_parse_failed"
        
        # Resolve gender once (single source of truth) and backfill it onto
        # the identity seed so the archive D1 gender (built from asdict below)
        # and the top-level M/F flag both match the name's gender. When the L2
        # seed already carries a gender (offline mock / cooperative live model)
        # it is honoured; otherwise fall back to a random draw.
        import numpy as _np
        _g = (identity_seed.gender or "").strip()
        if _g not in ("男", "女"):
            _g = str(_np.random.choice(["男", "女"]))
        identity_seed.gender = _g
        
        # Layer 3: Derive numerical fields + LLM narrative
        numerical_fields = Layer3DerivationEngine.derive_numerical_fields(
            skeleton, asdict(identity_seed)
        )
        
        if preset_narrative is not None:
            # Batched cohort path: narrative already generated.
            narrative_fields = preset_narrative
        else:
            narrative_prompt = Layer3DerivationEngine.get_narrative_continuation_prompt(
                asdict(identity_seed), numerical_fields
            )
            narrative_response = self.llm_func(narrative_prompt, temperature=0.7)
            narrative_fields = Layer3DerivationEngine.parse_narrative_output(narrative_response)
        
        # Full 23-domain archive (FR-A1: 210+ fields, coherent latent-derived)
        from .full_archive import build_full_archive
        full_archive = build_full_archive(
            skeleton, asdict(identity_seed), numerical_fields,
            seed=(seed if seed is not None else 42)
        )
        
        # Assemble student archive
        student_archive = {
            "student_id": student_id,
            "name": identity_seed.name,
            "gender": "M" if identity_seed.gender == "男" else "F",
            "birth_date": (datetime.now() - timedelta(days=365*14)).isoformat(),
            "birth_place": identity_seed.birth_place,
            "grade": 8,
            "family_structure": identity_seed.family_structure_type,
            "personality_tags": [identity_seed.core_personality_seed],
            "interests": narrative_fields.get("interests", []),
            "achievement_score": numerical_fields["achievement_score"],
            "study_habits_score": numerical_fields["study_habits_score"],
            "self_efficacy": numerical_fields["self_efficacy"],
            "family_investment_hours_weekly": numerical_fields["family_investment_hours_weekly"],
            "motivation_level": numerical_fields["motivation_level"],
            "time_allocation": narrative_fields.get("time_allocation", {
                "school": 0.45, "homework": 0.20, "self_study": 0.10, "recreation": 0.25
            }),
            "key_life_event": narrative_fields.get("key_life_event", ""),
            "teacher_interaction": narrative_fields.get("teacher_interaction_style", ""),
            
            # Simulation vector (for cognitive engine)
            "simulation_vector": {
                "p_know": skeleton["p_know"],
                "p_learn": skeleton["p_learn"],
                "p_slip": 0.1,
                "p_guess": 0.1,
                "misconception_type": skeleton.get("misconception_type", "代数"),
                "motivation": numerical_fields["motivation_level"],
                "self_efficacy": numerical_fields["self_efficacy"]
            },
            
            # Sensitive fields (S-level)
            "sensitive_data": {
                "health_status": "正常",
                "family_structure_detail": "两亲俱在，无特殊情况",
                "tutoring_cost_yearly": 5000 + int(np.random.normal(0, 2000))
            },
            
            # LLM traceability
            "llm_generated_fields": {
                "name": True,
                "birth_place": True,
                "family_structure_type": True,
                "personality_tags": True,
                "interests": True,
                "key_life_event": True,
                "time_allocation": True
            },
            
            "created_at": int(time.time() * 1000),
            
            # FR-A1: comprehensive 23-domain archive (210+ fields)
            "domains": full_archive["domains"],
            "field_count": full_archive["field_count"],
            "domain_count": full_archive["domain_count"],
            "sensitive_domains": full_archive["sensitive_domains"],
        }
        
        # Layer 4: Coherence validation + Uniqueness guarantee
        coherence_checks = Layer4CoherenceEngine.validate_coherence(student_archive)
        student_archive = Layer4CoherenceEngine.repair_inconsistencies(student_archive)
        
        # Uniqueness check (L4)
        unique_student, uniqueness_status = self.uniqueness_guarantor.ensure_unique(
            student_archive,
            regenerator_func=lambda: self.generate_student(student_id, seed)
        )
        
        if uniqueness_status != "unique_accepted":
            return unique_student, f"uniqueness_warning: {uniqueness_status}"
        
        return unique_student, "success"
    
    def _generate_identity_seed(self, skeleton: Dict) -> Optional[IdentitySeed]:
        """L2 identity-seed generation for a single student (per-student path).

        Retries until the generated name is unique within this generator's
        cohort. The L1 skeleton (calibrated cognitive params) stays fixed
        across attempts -- only the creative identity layer varies -- so
        same-seed runs remain fully reproducible. In LIVE mode the model is
        also handed the explicit list of already-used names to avoid. Returns
        None only if the LLM output cannot be parsed at all.
        """
        base_prompt = IdentitySeedGenerator.get_identity_seed_prompt(
            skeleton, batch_size=1
        )
        live = get_client().is_live
        identity_seeds = []
        for attempt in range(12):
            extra = ""
            if live and self._used_names:
                used = "、".join(sorted(self._used_names))
                extra += (
                    f"\n【姓名查重约束】以下姓名已被其他学生使用，本次生成的姓名"
                    f"必须与它们完全不同：{used}"
                )
            if live and attempt > 0:
                extra += (
                    f"\n【第 {attempt} 次重试】请务必改用一个全新的中文姓名"
                    f"（更换姓氏或名字用字），不要与上述已用姓名重复。"
                )
            if not live and attempt > 0:
                extra = f"\n[身份唯一性盐值 #{attempt}]"
            llm_response = self.llm_func(base_prompt + extra, temperature=1.0)
            identity_seeds = IdentitySeedGenerator.parse_llm_output(llm_response)
            if identity_seeds and identity_seeds[0].name not in self._used_names:
                break

        if not identity_seeds:
            return None

        identity_seed = identity_seeds[0]
        # Hard, LLM-independent uniqueness guarantee (FR-A10). No-op when the
        # name is already unique (the common case, and always in mock mode).
        identity_seed.name = self._force_unique_name(identity_seed.name)
        self._used_names.add(identity_seed.name)
        return identity_seed

    # ------------------------------------------------------------------
    # Batched cohort generation (live-mode speed optimisation)
    # ------------------------------------------------------------------
    def generate_cohort(self, n_students: int, base_seed: int = 42,
                        id_prefix: str = "S", batch_size: int = 8,
                        progress_callback=None) -> Dict[str, Dict]:
        """Generate a whole cohort, returning ``{student_id: archive}``.

        In LIVE mode the L2 identity seeds and L3 narratives are fetched in
        batches of ``batch_size`` per LLM call, so a 100-student cohort needs
        ~26 calls instead of 200+ (the per-student path also retries the L2
        call up to 12 times per student to keep names unique, which compounds
        the cost). Offline (no API key) it falls back to the per-student
        pipeline: mock calls are instant so batching buys nothing there, and
        keeping the per-student path preserves the seeded byte-for-byte
        reproducible output the test suite relies on.

        ``progress_callback`` (optional) is invoked as
        ``callback(fraction, message)`` with ``fraction`` in ``[0, 1]`` so the
        caller can surface live progress while the cohort is generated.
        """
        client = get_client()
        if client.is_live and not self._custom_llm:
            return self._generate_cohort_batched(
                n_students, base_seed, id_prefix, batch_size, progress_callback)

        students: Dict[str, Dict] = {}
        for i in range(n_students):
            sid = f"{id_prefix}{i:05d}"
            student, _status = self.generate_student(sid, seed=base_seed + i)
            if student is not None:
                students[sid] = student
            if progress_callback is not None:
                progress_callback((i + 1) / max(1, n_students),
                                  f"已生成 {i + 1}/{n_students} 名学生画像")
        return students

    def _generate_cohort_batched(self, n_students: int, base_seed: int,
                                 id_prefix: str, batch_size: int,
                                 progress_callback=None) -> Dict[str, Dict]:
        """Batched live-mode cohort generation (L2 + L3 batched per call)."""
        import numpy as np

        def report(frac, msg):
            if progress_callback is not None:
                progress_callback(frac, msg)

        # L1: one deterministic skeleton per student (identical sampling to the
        # per-student path, so cognitive parameters are unchanged).
        skeletons: List[Dict] = []
        for i in range(n_students):
            np.random.seed(base_seed + i)
            skeletons.append(
                Layer1SkeletonGenerator.sample_skeleton(self.posterior_dist))
        report(0.05, f"已采样 {n_students} 个 L1 认知骨架")

        # L2: identity seeds, batch_size per LLM call.
        n_batches = (n_students + batch_size - 1) // batch_size

        def _seed_batch_cb(done, total):
            report(0.05 + 0.40 * done / max(1, total),
                   f"生成身份种子（LLM）：第 {done}/{total} 批")

        identity_seeds = self._batch_identity_seeds(
            skeletons, batch_size, batch_callback=_seed_batch_cb)
        report(0.45, "身份种子生成完毕")

        # L3 (numerical): deterministic derivation per student. Re-seed so the
        # skeleton+derive random stream mirrors generate_student exactly, hence
        # the narrative context below matches each archive's numerical fields.
        numerical: List[Dict] = []
        for i in range(n_students):
            np.random.seed(base_seed + i)
            sk = Layer1SkeletonGenerator.sample_skeleton(self.posterior_dist)
            numerical.append(Layer3DerivationEngine.derive_numerical_fields(
                sk, asdict(identity_seeds[i])))
        report(0.50, "数值特征派生完毕")

        # L3 (narrative): batch_size per LLM call.
        def _narr_batch_cb(done, total):
            report(0.50 + 0.35 * done / max(1, total),
                   f"生成生活叙事（LLM）：第 {done}/{total} 批")

        narratives = self._batch_narratives(
            identity_seeds, numerical, batch_size, batch_callback=_narr_batch_cb)
        report(0.85, "叙事生成完毕，开始组装档案")

        # Assembly + L4 coherence/uniqueness per student (reuses the exact
        # per-student assembler via generate_student's preset hooks).
        students: Dict[str, Dict] = {}
        for i in range(n_students):
            sid = f"{id_prefix}{i:05d}"
            student, _status = self.generate_student(
                sid, seed=base_seed + i,
                preset_identity_seed=identity_seeds[i],
                preset_narrative=narratives[i])
            if student is not None:
                students[sid] = student
            if i % 10 == 0 or i == n_students - 1:
                report(0.85 + 0.15 * (i + 1) / max(1, n_students),
                       f"组装与一致性校验：{i + 1}/{n_students}")
        return students

    def _batch_identity_seeds(self, skeletons: List[Dict],
                              batch_size: int,
                              batch_callback=None) -> List[IdentitySeed]:
        """Generate identity seeds for the whole cohort, ``batch_size`` per LLM
        call. Always returns exactly ``len(skeletons)`` seeds: any batch that
        under-delivers (parse failure / rate limit) is topped up with
        deterministic fallback seeds so the cohort is never short.

        ``batch_callback`` (optional) is invoked as ``(done_batches, total)``
        after each batch so callers can report live progress."""
        seeds: List[IdentitySeed] = []
        n = len(skeletons)
        total_batches = (n + batch_size - 1) // batch_size
        done_batches = 0
        for start in range(0, n, batch_size):
            chunk = skeletons[start:start + batch_size]
            k = len(chunk)
            prompt = IdentitySeedGenerator.get_identity_seed_prompt(
                chunk[0], batch_size=k)
            if self._used_names:
                used = "、".join(sorted(self._used_names))
                prompt += (
                    f"\n【姓名查重约束】以下姓名已被其他学生使用，本批生成的姓名"
                    f"必须与它们完全不同：{used}"
                )
            try:
                raw = self.llm_func(prompt, temperature=1.0, max_tokens=3000)
                parsed = IdentitySeedGenerator.parse_llm_output(raw)
            except Exception as e:
                print(f"[LLM] batch identity-seed call failed "
                      f"({type(e).__name__}: {e}); using deterministic "
                      f"fallback for this batch", flush=True)
                parsed = []
            for j in range(k):
                seed = (parsed[j] if (j < len(parsed)) and parsed[j].name
                        else self._fallback_seed(chunk[j]))
                seed.name = self._force_unique_name(seed.name)
                self._used_names.add(seed.name)
                seeds.append(seed)
            done_batches += 1
            if batch_callback is not None:
                batch_callback(done_batches, total_batches)
        return seeds

    def _fallback_seed(self, skeleton: Dict) -> IdentitySeed:
        """Deterministic offline-style identity seed used to top up a batch that
        under-delivered, so the cohort always has a full set of unique seeds."""
        prompt = IdentitySeedGenerator.get_identity_seed_prompt(
            skeleton, batch_size=1)
        parsed = IdentitySeedGenerator.parse_llm_output(
            self._mock_llm(prompt, temperature=1.0))
        if parsed:
            return parsed[0]
        return IdentitySeed(
            name="学某", birth_place="县城", family_structure_type="完整家庭",
            core_personality_seed="内向但执着，擅长独立思考",
            unique_life_seed="一次独特的生活事件塑造了其学习态度。")

    def _batch_narratives(self, identity_seeds: List[IdentitySeed],
                          numerical: List[Dict],
                          batch_size: int,
                          batch_callback=None) -> List[Dict]:
        """Generate L3 narratives for the whole cohort, ``batch_size`` per LLM
        call. Returns exactly ``len(identity_seeds)`` dicts; any batch that
        under-delivers falls back to empty dicts (the assembler supplies sane
        defaults for every narrative field).

        ``batch_callback`` (optional) is invoked as ``(done_batches, total)``
        after each batch so callers can report live progress."""
        narratives: List[Dict] = []
        n = len(identity_seeds)
        total_batches = (n + batch_size - 1) // batch_size
        done_batches = 0
        for start in range(0, n, batch_size):
            k = min(batch_size, n - start)
            prompt = self._narrative_batch_prompt(
                identity_seeds, numerical, start, k)
            try:
                raw = self.llm_func(prompt, temperature=0.7, max_tokens=6000)
                parsed = json.loads(_strip_json_fences(raw))
                if isinstance(parsed, dict) and "narratives" in parsed:
                    parsed = parsed["narratives"]
                if not isinstance(parsed, list):
                    parsed = []
            except Exception as e:
                print(f"[LLM] batch narrative call failed "
                      f"({type(e).__name__}: {e}); using empty narratives "
                      f"for this batch", flush=True)
                parsed = []
            for j in range(k):
                narratives.append(
                    parsed[j] if (j < len(parsed) and isinstance(parsed[j], dict))
                    else {})
            done_batches += 1
            if batch_callback is not None:
                batch_callback(done_batches, total_batches)
        return narratives

    @staticmethod
    def _narrative_batch_prompt(identity_seeds: List[IdentitySeed],
                                numerical: List[Dict],
                                start: int, k: int) -> str:
        """Build one L3 narrative prompt covering ``k`` students (order-preserving)."""
        blocks = []
        for idx in range(start, start + k):
            s = identity_seeds[idx]
            nf = numerical[idx]
            blocks.append(
                f"学生{idx - start + 1}:\n"
                f"- 名字: {s.name}\n"
                f"- 出生地: {s.birth_place}\n"
                f"- 家庭结构: {s.family_structure_type}\n"
                f"- 核心人格: {s.core_personality_seed}\n"
                f"- 独特经历: {s.unique_life_seed}\n"
                f"- 成绩: {nf.get('achievement_score', 0):.1f}/100, "
                f"学习习惯: {nf.get('study_habits_score', 0.5):.2f}, "
                f"自我效能: {nf.get('self_efficacy', 0.5):.2f}, "
                f"动机: {nf.get('motivation_level', 0.5):.2f}"
            )
        students_text = "\n\n".join(blocks)
        return f"""基于以下 {k} 个虚拟学生各自的身份证与数值特征，分别为每人生成生活叙事。

{students_text}

【生成要求】
1. 为每个学生输出一个叙事对象，字段含义与单个学生一致：
   key_life_event（关键经历，200-300字）、interests（3-5个兴趣的数组）、
   teacher_interaction_style（师生互动风格，50-100字）、
   time_allocation（school/homework/self_study/recreation 四项百分比，和为1）、
   narrative_summary（100字总结）。
2. {k} 个学生的叙事必须各不相同，且与各自的人格和成绩水平一致。

【输出格式】
仅输出一个 JSON 数组，包含 {k} 个对象，顺序与上面的学生顺序一致：
[
  {{"key_life_event": "...", "interests": ["..."], "teacher_interaction_style": "...", "time_allocation": {{"school": 0.45, "homework": 0.20, "self_study": 0.10, "recreation": 0.25}}, "narrative_summary": "..."}}
]

开始生成：
"""

    def generate_batch(self, n: int, start_id: str = "S", base_seed: int = 42) -> List[Dict]:
        """
        Generate batch of students
        
        Args:
            n: Number of students
            start_id: ID prefix (e.g., "S001", "S002", ...)
            base_seed: Random seed for reproducibility
            
        Returns:
            List of student archives
        """
        import numpy as np
        students = []
        
        for i in range(n):
            student_id = f"{start_id}{i+1:04d}"
            seed = base_seed + i
            
            student, status = self.generate_student(student_id, seed)
            if student:
                students.append(student)
                if (i + 1) % 10 == 0:
                    print(f"Generated {i+1}/{n} students...")
            else:
                print(f"Failed to generate {student_id}: {status}")
        
        return students


if __name__ == "__main__":
    # Test: Generate 5 sample students
    generator = StudentGenerator()
    students = generator.generate_batch(5, start_id="DEMO")
    
    print(f"\nGenerated {len(students)} students:")
    for s in students:
        print(f"  - {s['student_id']}: {s['name']} (成绩: {s['achievement_score']:.1f})")
    
    # Save to JSON for inspection
    with open("sample_students.json", "w", encoding="utf-8") as f:
        json.dump(students, f, indent=2, ensure_ascii=False)
    print(f"\nSaved to sample_students.json")
