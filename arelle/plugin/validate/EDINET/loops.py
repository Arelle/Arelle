from arelle.ModelDtsObject import ModelRelationship


def directedCycle(val, fromObject, origin, fromRelationships, path) -> None | list[ModelRelationship]:
    if fromObject in fromRelationships:
        for rel in fromRelationships[fromObject]:
            toObject = rel.toModelObject
            if toObject == origin:
                return [rel]
            if toObject not in path: # report cycle only where origin causes the cycle
                path.add(toObject)
                foundCycle = directedCycle(val, toObject, origin, fromRelationships, path)
                if foundCycle is not None:
                    foundCycle.insert(0, rel)
                    return foundCycle
                path.discard(toObject)
