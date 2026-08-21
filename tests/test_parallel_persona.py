"""Live-LLM cohort generation must run batches concurrently; offline and
test-injected LLMs stay sequential."""
import json as _json
import threading
import time

import src.llm as llm_module
from src.persona_service.student_generator import StudentGenerator


def test_cohort_batches_run_in_parallel_when_live(monkeypatch):
    gen = StudentGenerator()

    class FakeLive:
        is_live = True

        def __init__(self):
            self.lock = threading.Lock()
            self.cur = 0
            self.maxc = 0
            self.calls = 0

        def call(self, prompt, temperature=0.7, max_tokens=2000, **kwargs):
            with self.lock:
                self.cur += 1
                self.maxc = max(self.maxc, self.cur)
                self.calls += 1
            time.sleep(0.15)
            with self.lock:
                self.cur -= 1
            return gen._mock_llm(prompt, temperature)

    fake = FakeLive()
    monkeypatch.setattr(llm_module, "_default_client", fake)

    t0 = time.time()
    students = gen.generate_cohort(16, base_seed=7, batch_size=4)
    dt = time.time() - t0

    assert len(students) == 16
    assert fake.calls >= 8  # 4 seed batches + 4 narrative batches
    assert fake.maxc >= 2, "LLM batches did not run concurrently"
    assert dt < 2.0, f"parallel cohort generation too slow: {dt:.2f}s"


def test_cohort_sequential_with_injected_llm():
    calls = []

    def fake_llm(prompt, temperature=0.7, max_tokens=2000, **kwargs):
        calls.append(1)
        gen = fake_llm.__dict__.setdefault("_gen", StudentGenerator())
        return gen._mock_llm(prompt, temperature)

    gen = StudentGenerator(llm_func=fake_llm)
    students = gen.generate_cohort(8, base_seed=3, batch_size=4)
    assert len(students) == 8
    assert len(calls) >= 4


def test_teacher_parent_parallel_and_batched_narratives(monkeypatch):
    from src.persona_service.teacher_parent_generator import (
        TeacherGenerator, ParentGenerator)

    class FakeLive:
        is_live = True

        def __init__(self):
            self.lock = threading.Lock()
            self.cur = 0
            self.maxc = 0
            self.calls = 0

        def call(self, prompt, temperature=0.7, max_tokens=2000, **kwargs):
            with self.lock:
                self.cur += 1
                self.maxc = max(self.maxc, self.cur)
                self.calls += 1
            time.sleep(0.1)
            with self.lock:
                self.cur -= 1
            return _json.dumps([f"观念{i}" for i in range(16)],
                               ensure_ascii=False)

    fake = FakeLive()
    monkeypatch.setattr(llm_module, "_default_client", fake)

    teachers = TeacherGenerator.generate_batch(6)
    assert len(teachers) == 6
    assert fake.maxc >= 2, "teacher generation did not run concurrently"

    fake.calls = 0
    fake.maxc = 0
    parents = ParentGenerator.generate_batch_for_students(10, 6)
    assert len(parents) == 10
    assert fake.calls == 2, f"expected 2 batched narrative calls, got {fake.calls}"
    assert any("parenting_narrative" in p for p in parents)


def test_parent_offline_stays_narrative_free(monkeypatch):
    from src.persona_service.teacher_parent_generator import ParentGenerator

    class FakeOffline:
        is_live = False

    monkeypatch.setattr(llm_module, "_default_client", FakeOffline())
    parents = ParentGenerator.generate_batch_for_students(6, 4)
    assert len(parents) == 6
    assert all("parenting_narrative" not in p for p in parents)
