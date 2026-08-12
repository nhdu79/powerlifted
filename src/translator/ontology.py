from normalize import all_conditions

def collect_all_mkos(task):
    mkos = set()
    for proxy in all_conditions(task):
        proxy.condition.collect_mkos(mkos)
    return list(mkos)

def process_ontology(task, ontology_filename):
    """Hi @Duy, here would be a natural entry point for you."""
    mkos = collect_all_mkos(task)
    print()
    print("All mkos")
    for mko in mkos:
        mko.dump()
