from arelle.formula.FactAspectsCache import FactAspectsCache


class TestFactAspectsCache:
    def test_match(self):
        cache = FactAspectsCache(10)
        cache.cacheMatch("fact1", "fact2", "aspect")

        fact1_evaluations = cache.evaluations("fact1", "fact2")
        fact2_evaluations = cache.evaluations("fact2", "fact1")

        assert all(evaluations == {"aspect": True} for evaluations in (fact1_evaluations, fact2_evaluations))

    def test_cache_none_values(self):
        cache = FactAspectsCache(10)

        cache.cacheNotMatch(None, "fact2", "aspect")
        cache.cacheNotMatch("fact1", None, "aspect")
        cache.cacheNotMatch("fact1", "fact2", None)

        fact1_2_evaluations = cache.evaluations("fact1", "fact2")
        fact1_none_evaluations = cache.evaluations("fact1", None)
        fact2_none_evaluations = cache.evaluations(None, "fact2")

        assert fact1_2_evaluations == {
            None: False,
        }

        assert fact1_none_evaluations == {
            "aspect": False,
        }

        assert fact2_none_evaluations == {
            "aspect": False,
        }

    def test_non_match(self):
        cache = FactAspectsCache(10)
        cache.cacheNotMatch("fact1", "fact2", "aspect")

        fact1_evaluations = cache.evaluations("fact1", "fact2")
        fact2_evaluations = cache.evaluations("fact2", "fact1")

        assert all(evaluations == {"aspect": False} for evaluations in (fact1_evaluations, fact2_evaluations))

    def test_mixed_evaluations(self):
        cache = FactAspectsCache(10)
        cache.cacheMatch("fact1", "fact2", "aspect1")
        cache.cacheNotMatch("fact1", "fact2", "aspect2")

        evaluations = cache.evaluations("fact1", "fact2")

        assert evaluations == {
            "aspect1": True,
            "aspect2": False,
        }

    def test_empty_cache(self):
        cache = FactAspectsCache(10)

        evaluations = cache.evaluations("fact1", "fact2")

        assert evaluations is None

    def test_additional_facts(self):
        cache = FactAspectsCache(10)

        cache.cacheMatch("fact1", "fact2", "aspect1")
        cache.cacheNotMatch("fact1", "fact2", "aspect2")
        cache.cacheMatch("fact1", "fact2", "aspect3")

        cache.cacheNotMatch("fact1", "fact3", "aspect1")
        cache.cacheMatch("fact1", "fact3", "aspect2")

        cache.cacheNotMatch("fact2", "fact3", "aspect1")

        evaluations = cache.evaluations("fact1", "fact2")

        assert evaluations == {
            "aspect1": True,
            "aspect2": False,
            "aspect3": True,
        }

    def test_max_size_reached(self):
        cache = FactAspectsCache(2)
        cache.cacheNotMatch("fact1", "fact2", "aspect1")
        cache.cacheMatch("fact1", "fact2", "aspect2")

        evaluations = cache.evaluations("fact1", "fact2")

        assert evaluations == {
            "aspect1": False,
            "aspect2": True,
        }
        assert cache.prioritizedAspects == {"aspect1"}

        cache.cacheNotMatch("fact1", "fact2", "aspect3")

        evaluations = cache.evaluations("fact1", "fact2")

        assert evaluations == {
            "aspect1": False,
            "aspect2": True,
        }
        assert cache.prioritizedAspects == {"aspect1", "aspect3"}

    def test_negative_max_size(self):
        cache = FactAspectsCache(-1)
        for i in range(100):
            cache.cacheNotMatch("fact1", "fact2", f"aspect{i}")

        evaluations = cache.evaluations("fact1", "fact2")

        assert evaluations == {
            f"aspect{i}": False
            for i in range(100)
        }
        assert cache.prioritizedAspects == {
            f"aspect{i}"
            for i in range(100)
        }

    def test_zero_max_size(self):
        cache = FactAspectsCache(0)
        cache.cacheNotMatch("fact1", "fact2", "aspect")

        evaluations = cache.evaluations("fact1", "fact2")

        assert evaluations is None
        assert cache.prioritizedAspects == {"aspect"}

    def test_clear(self):
        cache = FactAspectsCache(10)
        cache.cacheMatch("fact1", "fact2", "aspect")

        evaluations = cache.evaluations("fact1", "fact2")

        assert evaluations == {
            "aspect": True,
        }

        cache.clear()
        evaluations = cache.evaluations("fact1", "fact2")

        assert evaluations is None

    def test_prioritized_aspects(self):
        cache = FactAspectsCache(10)
        cache.cacheNotMatch("fact1", "fact2", "aspect1")
        cache.cacheNotMatch("fact1", "fact2", "aspect2")
        cache.cacheMatch("fact1", "fact2", "aspect3")
        cache.cacheMatch("fact1", "fact2", "aspect4")
        cache.cacheNotMatch("fact3", "fact4", "aspect5")

        assert cache.prioritizedAspects == {"aspect1", "aspect2", "aspect5"}

    def test_prioritized_aspects_clear(self):
        cache = FactAspectsCache(10)
        cache.cacheNotMatch("fact1", "fact2", "aspect1")

        assert cache.prioritizedAspects == {"aspect1"}

        cache.clear()

        assert cache.prioritizedAspects == set()

        cache.cacheNotMatch("fact1", "fact2", "aspect1")

        assert cache.prioritizedAspects == {"aspect1"}
