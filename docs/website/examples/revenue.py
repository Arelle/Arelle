from arelle.RuntimeOptions import RuntimeOptions
from arelle.api.Session import Session

options = RuntimeOptions(
    entrypointFile="demo-20251231.xbrl",
    keepOpen=True,
    logLevel="warning",
)

with Session() as session:
    session.run(options)
    for report in session.get_models():
        if modelDocument := report.modelDocument:
            print(f"{modelDocument.basename}:")
        for fact in report.factsByLocalName.get("Revenue", ()):
            if context := fact.context:
                print(f"{context.endDate},{fact.effectiveValue}")
