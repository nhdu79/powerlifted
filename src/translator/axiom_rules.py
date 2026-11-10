import pddl
import sccs
from pddl_parser import ParseError

from collections import defaultdict
from itertools import chain

# This file has been taken from Fast Downward. The original variant operates on
# instantiated axioms. It also removes unnecessary axioms and supports some
# additional verification (removed in this version).

DEBUG = False

class AxiomDependencies(object):
    def __init__(self, axioms):
        # Assumes that axiom conditions have been normalized, so they are
        # conjunctions of literals.
        self.derived_predicates = {axiom.name for axiom in axioms}
        self.positive_dependencies = defaultdict(set)
        self.negative_dependencies = defaultdict(set)
        for axiom in axioms:
            head_pred = axiom.name
            if isinstance(axiom.condition, pddl.Conjunction):
                literals = axiom.condition.parts
            else:
                literals = [axiom.condition]
            if DEBUG:
                assert all(isinstance(literal, pddl.Literal) for literal in literals)
            for body_literal in literals:
                if body_literal.predicate in self.derived_predicates:
                    if body_literal.negated:
                        self.negative_dependencies[head_pred].add(body_literal.predicate)
                    else:
                        self.positive_dependencies[head_pred].add(body_literal.predicate)


class AxiomCluster(object):
    def __init__(self, derived_predicates):
        self.predicates = derived_predicates
        self.axioms = dict((p, []) for p in derived_predicates)
        # Positive children will be populated with clusters that contain an
        # predicate that occurs in the body of an axiom whose head is from this
        # cluster. Negative children analogous for predicates that occur negated
        # in the body.
        self.positive_children = set()
        self.negative_children = set()
        self.layer = 0

    def set_layer(self, layer):
        self.layer = layer
        for _, axioms in self.axioms.items():
            for ax in axioms:
                ax.layer = layer

def handle_axioms(axioms, layer_strategy):
    clusters = compute_clusters(axioms)
    axiom_layers = compute_axiom_layers(clusters, layer_strategy)
    return axiom_layers


# Compute strongly connected components of the dependency graph.
# In order to receive a deterministic result, we first sort the variables.
# We then build adjacency lists over the variable indices based on dependencies.
def get_strongly_connected_components(dependencies):
    sorted_preds = sorted(dependencies.derived_predicates)
    predicate_to_index = {var: index for index, var in enumerate(sorted_preds)}

    adjacency_list = []
    for derived_pred in sorted_preds:
        pos = dependencies.positive_dependencies[derived_pred]
        neg = dependencies.negative_dependencies[derived_pred]
        indices = [predicate_to_index[pred] for pred in sorted(pos.union(neg))]
        adjacency_list.append(indices)

    index_groups = sccs.get_sccs_adjacency_list(adjacency_list)
    groups = [[sorted_preds[i] for i in g] for g in index_groups]
    return groups

def compute_clusters(axioms):
    dependencies = AxiomDependencies(axioms)

    groups = get_strongly_connected_components(dependencies)
    clusters = [AxiomCluster(group) for group in groups]

    # Compute mapping from predicates to their clusters.
    predicate_to_cluster = {}
    for cluster in clusters:
        for predicate in cluster.predicates:
            predicate_to_cluster[predicate] = cluster

    # Assign axioms to their clusters.
    for axiom in axioms:
        predicate_to_cluster[axiom.name].axioms[axiom.name].append(axiom)

    # Create links between clusters (positive dependencies).
    for from_pred, depends_on in dependencies.positive_dependencies.items():
        from_cluster = predicate_to_cluster[from_pred]
        for to_pred in depends_on:
            to_cluster = predicate_to_cluster[to_pred]
            if from_cluster is not to_cluster:
                from_cluster.positive_children.add(to_cluster)

    # Create links between clusters (negative dependencies).
    for from_pred, depends_on in dependencies.negative_dependencies.items():
        from_cluster = predicate_to_cluster[from_pred]
        for to_pred in depends_on:
            to_cluster = predicate_to_cluster[to_pred]
            if from_cluster is to_cluster:
                raise Error("Error: The axioms are not stratifiable.")
            from_cluster.negative_children.add(to_cluster)

    return clusters


# Assign every cluster the smallest possible layer.
def compute_single_cluster_layer(cluster):
    layer = 0
    for pos_child in cluster.positive_children:
        layer = max(pos_child.layer, layer)
    for neg_child in cluster.negative_children:
        layer = max(neg_child.layer + 1, layer)
    return layer


# Clusters must be ordered topologically based on AxiomDependencies.
# Since we need to visit clusters containing variables that occur in the body
# of an atom before we visit the cluster containing the head, we need to
# traverse the clusters in reverse order.
def compute_axiom_layers(clusters, strategy):
    if strategy == "max":
        layer = 0
        for cluster in reversed(clusters):
            cluster.set_layer(layer)
            layer += 1
    elif strategy == "min":
        for cluster in reversed(clusters):
            cluster.set_layer(compute_single_cluster_layer(cluster))
