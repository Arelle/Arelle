from arelle.formula.FactAspectsCache import FactAspectsCache


class TestFactAspectsCache:
    def test_match(self):
        cache = FactAspectsCache()
        cache.cacheMatch("fact1", "fact2", "aspect")

        fact1_evaluations = cache.evaluations("fact1", "fact2")
        fact2_evaluations = cache.evaluations("fact2", "fact1")

        assert all(evaluations == {"aspect": True} for evaluations in (fact1_evaluations, fact2_evaluations))

    def test_non_match(self):
        cache = FactAspectsCache()
        cache.cacheNotMatch("fact1", "fact2", "aspect")

        fact1_evaluations = cache.evaluations("fact1", "fact2")
        fact2_evaluations = cache.evaluations("fact2", "fact1")

        assert all(evaluations == {"aspect": False} for evaluations in (fact1_evaluations, fact2_evaluations))

    def test_mixed_evaluations(self):
        cache = FactAspectsCache()
        cache.cacheMatch("fact1", "fact2", "aspect1")
        cache.cacheNotMatch("fact1", "fact2", "aspect2")

        evaluations = cache.evaluations("fact1", "fact2")

        assert evaluations == {
            "aspect1": True,
            "aspect2": False,
        }

    def test_empty_cache(self):
        cache = FactAspectsCache()

        evaluations = cache.evaluations("fact1", "fact2")

        assert evaluations == {}

    def test_additional_facts(self):
        cache = FactAspectsCache()

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

    def test_clear(self):
        cache = FactAspectsCache()
        cache.cacheMatch("fact1", "fact2", "aspect")

        evaluations = cache.evaluations("fact1", "fact2")

        assert evaluations == {
            "aspect": True,
        }

        cache.clear()
        evaluations = cache.evaluations("fact1", "fact2")

        assert evaluations == {}

    def test_prioritized_aspects(self):
        cache = FactAspectsCache()
        cache.cacheNotMatch("fact1", "fact2", "aspect1")
        cache.cacheNotMatch("fact1", "fact2", "aspect2")
        cache.cacheMatch("fact1", "fact2", "aspect3")
        cache.cacheMatch("fact1", "fact2", "aspect4")
        cache.cacheNotMatch("fact3", "fact4", "aspect5")

        assert cache.prioritizedAspects == {"aspect1", "aspect2", "aspect5"}

    def test_prioritized_aspects_clear(self):
        cache = FactAspectsCache()
        cache.cacheNotMatch("fact1", "fact2", "aspect1")

        assert cache.prioritizedAspects == {"aspect1"}

        cache.clear()

        assert cache.prioritizedAspects == set()

        cache.cacheNotMatch("fact1", "fact2", "aspect1")

        assert cache.prioritizedAspects == {"aspect1"}
