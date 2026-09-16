from normalize import all_conditions
from owl import ensure_fully_supported, normalize_ontology, parse_owl


def collect_all_mkos(task):
    mkos = set()
    for proxy in all_conditions(task):
        proxy.condition.collect_mkos(mkos)
    return list(mkos)


def process_ontology(task, ontology_filepath):
    """Parse, normalize, and validate the ontology for planning use. Raises
    owl.UnsupportedConstructError (via ensure_fully_supported) if any part
    of it didn't normalize into Table 1 form — this is the point at which
    an unsupported ontology aborts, since it's about to actually be used."""
    mkos = collect_all_mkos(task)
    ontology = parse_owl(ontology_filepath)

    print("All mkos")
    for mko in mkos:
        mko.dump()

    normalize_ontology(ontology)
    ensure_fully_supported(ontology)

    return ontology
