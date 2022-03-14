from databases import uniprot
from download import download

ORGANISM = {
    "data": {
        9606: "Homo sapiens"
    },
    "file": {
        9606: "homo_sapiens",
    }
}


def get_proteins(
    interaction_type=[],
    interaction_context=[],
    taxon_identifier=9606,
):
    primary_accession = uniprot.get_primary_accession(taxon_identifier)

    for row in download.tabular_txt(
            "https://reactome.org/download/current/interactors/reactome.{organism}.interactions.tab-delimited.txt"
            .format(organism=ORGANISM["file"].get(taxon_identifier,
                                                  "all_species")),
            delimiter="\t",
            header=0,
            usecols=[
                "# Interactor 1 uniprot id",
                "Interactor 2 uniprot id",
                "Interaction type",
                "Interaction context",
            ],
    ):
        if (row["# Interactor 1 uniprot id"].split(":")[0] == "uniprotkb" and
                row["Interactor 2 uniprot id"].split(":")[0] == "uniprotkb"):
            interactor_a = row["# Interactor 1 uniprot id"].split(":")[1]
            interactor_b = row["Interactor 2 uniprot id"].split(":")[1]

            if (not interaction_type
                    or row["Interaction type"] in interaction_type) and (
                        not interaction_context
                        or row["Interaction context"] in interaction_context):
                for primary_interactor_a in primary_accession.get(
                        interactor_a, {interactor_a}):
                    for primary_interactor_b in primary_accession.get(
                            interactor_b, {interactor_b}):
                        yield (primary_interactor_a, primary_interactor_b)


def get_protein_protein_interactions(
    interaction_type=[],
    interaction_context=[],
    taxon_identifier=9606,
):
    primary_accession = uniprot.get_primary_accession(taxon_identifier)

    for row in download.tabular_txt(
            "https://reactome.org/download/current/interactors/reactome.{organism}.interactions.tab-delimited.txt"
            .format(organism=ORGANISM["file"].get(taxon_identifier,
                                                  "all_species")),
            delimiter="\t",
            header=0,
            usecols=[
                "# Interactor 1 uniprot id",
                "Interactor 2 uniprot id",
                "Interaction type",
                "Interaction context",
            ],
    ):
        if (row["# Interactor 1 uniprot id"].split(":")[0] == "uniprotkb" and
                row["Interactor 2 uniprot id"].split(":")[0] == "uniprotkb"):
            interactor_a = row["# Interactor 1 uniprot id"].split(":")[1]
            interactor_b = row["Interactor 2 uniprot id"].split(":")[1]

            if ((not interaction_type
                 or row["Interaction type"] in interaction_type) and
                (not interaction_context
                 or row["Interaction context"] in interaction_context)):

                for primary_interactor_a in primary_accession.get(
                        interactor_a, {interactor_a}):
                    for primary_interactor_b in primary_accession.get(
                            interactor_b, {interactor_b}):
                        yield (primary_interactor_a, primary_interactor_b)


def get_pathways(taxon_identifier=0):
    for row in download.tabular_txt(
            "https://reactome.org/download/current/ReactomePathways.txt",
            delimiter="\t",
            usecols=[0, 1, 2]):
        if not taxon_identifier or row[2] == ORGANISM["data"].get(
                taxon_identifier):
            yield (row[0], row[1])


def get_pathway_relations():
    for row in download.tabular_txt(
            "https://reactome.org/download/current/ReactomePathwaysRelation.txt",
            delimiter="\t",
            usecols=[0, 1]):
        yield (row[0], row[1])


def get_pathway_map(taxon_identifier=0):
    primary_accession = uniprot.get_primary_accession(taxon_identifier)

    for row in download.tabular_txt(
            "https://reactome.org/download/current/UniProt2Reactome_All_Levels.txt",
            delimiter="\t",
            usecols=[0, 1, 5]):
        if not taxon_identifier or row[5] == ORGANISM["data"].get(
                taxon_identifier):
            for protein in primary_accession.get(row[0], {row[0]}):
                yield protein, row[1]
