from arelle.formula.FactAspectsCache import FactAspectsMatchCache


class TestFactAspectsMatchCache:
    def test_match(self):
        cache = FactAspectsMatchCache()
        cache.cacheMatch("fact1", "fact2", "aspect")

        fact1_evaluations = cache.evaluations("fact1", "fact2")
        fact2_evaluations = cache.evaluations("fact2", "fact1")

        assert all(evaluations == {"aspect": True} for evaluations in (fact1_evaluations, fact2_evaluations))

    def test_non_match(self):
        cache = FactAspectsMatchCache()
        cache.cacheNotMatch("fact1", "fact2", "aspect")

        fact1_evaluations = cache.evaluations("fact1", "fact2")
        fact2_evaluations = cache.evaluations("fact2", "fact1")

        assert all(evaluations == {"aspect": False} for evaluations in (fact1_evaluations, fact2_evaluations))

    def test_mixed_evaluations(self):
        cache = FactAspectsMatchCache()
        cache.cacheMatch("fact1", "fact2", "aspect1")
        cache.cacheNotMatch("fact1", "fact2", "aspect2")

        evaluations = cache.evaluations("fact1", "fact2")

        assert evaluations == {
            "aspect1": True,
            "aspect2": False,
        }

    def test_empty_cache(self):
        cache = FactAspectsMatchCache()

        evaluations = cache.evaluations("fact1", "fact2")

        assert evaluations == {}

    def test_additional_facts(self):
        cache = FactAspectsMatchCache()

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
