#pragma once

#include "konclude_embedded.h"

#include <string>
#include <vector>

class KoncludeReasoner {
public:
    KoncludeReasoner() : handle_(konclude_create_reasoner()) {}
    ~KoncludeReasoner() { konclude_destroy_reasoner(handle_); }
    KoncludeReasoner(const KoncludeReasoner &) = delete;
    KoncludeReasoner &operator=(const KoncludeReasoner &) = delete;

    bool ok() const { return handle_ != nullptr; }

    bool loadOntology(const std::string &path)
    { return konclude_load_ontology_file(handle_, path.c_str()); }

    bool tellAndRetract(const std::vector<KoncludeClassAssertion> &tell,
                        const std::vector<KoncludeClassAssertion> &retract)
    {
        return konclude_tell_and_retract_axioms(handle_,
                                                tell.data(),
                                                static_cast<int>(tell.size()),
                                                retract.data(),
                                                static_cast<int>(retract.size()));
    }

    bool query(const std::string &sparql)
    { return konclude_execute_conjunctive_query(handle_, sparql.c_str()); }

    const char *lastError() const { return konclude_last_error(handle_); }

private:
    KoncludeReasonerHandle handle_;
};
