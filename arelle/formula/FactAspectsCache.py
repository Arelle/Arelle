from collections import defaultdict


class FactAspectsCache:
    def __init__(self):
        self._matchingAspects = defaultdict(lambda : defaultdict(dict))

    def evaluations(self, fact1, fact2):
        return self._matchingAspects[fact1][fact2]

    def cacheMatch(self, fact1, fact2, aspect):
        self._register(fact1, fact2, aspect, True)

    def cacheNotMatch(self, fact1, fact2, aspect):
        self._register(fact1, fact2, aspect, False)

    def _register(self, fact1, fact2, aspect, value):
        self._matchingAspects[fact1][fact2][aspect] = value
        self._matchingAspects[fact2][fact1][aspect] = value

    def clear(self):
        self._matchingAspects.clear()

    def __repr__(self):
        return f"FactAspectsCache(matchingAspects={self._matchingAspects})"
