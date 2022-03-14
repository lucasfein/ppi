from databases import uniprot
from download import download

ORGANISM = {"file": {9606: "Homo_sapiens"}}


def get_proteins(
    experimental_system=[],
    experimental_system_type=[],
    interaction_throughput=[],
    multi_validated_physical=False,
    taxon_identifier=9606,
):
    primary_accession = uniprot.get_primary_accession(taxon_identifier)

    for row in download.tabular_txt(
            "https://downloads.thebiogrid.org/Download/BioGRID/Latest-Release/BIOGRID-MV-Physical-LATEST.tab3.zip"
            if multi_validated_physical else
            "https://downloads.thebiogrid.org/Download/BioGRID/Latest-Release/BIOGRID-ORGANISM-LATEST.tab3.zip",
            file_from_zip_archive=
            r"BIOGRID-MV-Physical-[0-9]\.[0-9]\.[0-9]{3}\.tab3\.txt"
            if multi_validated_physical else
            r"BIOGRID-ORGANISM-{organism}-[0-9]\.[0-9]\.[0-9][0-9][0-9]\.tab3\.txt"
            .format(organism=ORGANISM["file"][taxon_identifier]),
            delimiter="\t",
            header=0,
            usecols=[
                "Experimental System", "Experimental System Type",
                "Organism ID Interactor A", "Organism ID Interactor B",
                "Throughput"
                "SWISS-PROT Accessions Interactor A",
                "SWISS-PROT Accessions Interactor B"
            ],
    ):
        if (row["SWISS-PROT Accessions Interactor A"] == "-"
                or row["SWISS-PROT Accessions Interactor B"] == "-"):
            continue

        if ((not experimental_system
             or row["Experimental System"] in experimental_system) and
            (not experimental_system_type
             or row["Experimental System Type"] in experimental_system_type)
                and row["Organism ID Interactor A"] == taxon_identifier
                and row["Organism ID Interactor B"] == taxon_identifier
                and (not interaction_throughput
                     or any(it in interaction_throughput
                            for it in row["Throughput"].split("|")))):
            for interactor_a in row[
                    "SWISS-PROT Accessions Interactor A"].split("|"):

                if "-" in interactor_a and not interactor_a.split(
                        "-")[1].isnumeric():
                    interactor_a = interactor_a.split("-")[0]

                for interactor_b in row[
                        "SWISS-PROT Accessions Interactor B"].split("|"):

                    if "-" in interactor_b and not interactor_b.split(
                            "-")[1].isnumeric():
                        interactor_b = interactor_b.split("-")[0]

                    for primary_interactor_a in primary_accession.get(
                            interactor_a, {interactor_a}):
                        for primary_interactor_b in primary_accession.get(
                                interactor_b, {interactor_b}):
                            yield (primary_interactor_a, primary_interactor_b)


def get_protein_protein_interactions(
    experimental_system=[],
    experimental_system_type=[],
    interaction_throughput=[],
    multi_validated_physical=False,
    taxon_identifier=9606,
):
    primary_accession = uniprot.get_primary_accession(taxon_identifier)

    for row in download.tabular_txt(
            "https://downloads.thebiogrid.org/Download/BioGRID/Latest-Release/BIOGRID-MV-Physical-LATEST.tab3.zip"
            if multi_validated_physical else
            "https://downloads.thebiogrid.org/Download/BioGRID/Latest-Release/BIOGRID-ORGANISM-LATEST.tab3.zip",
            file_from_zip_archive=
            r"BIOGRID-MV-Physical-[0-9]\.[0-9]\.[0-9]{3}\.tab3\.txt"
            if multi_validated_physical else
            r"BIOGRID-ORGANISM-{organism}-[0-9]\.[0-9]\.[0-9][0-9][0-9]\.tab3\.txt"
            .format(organism=ORGANISM["file"][taxon_identifier]),
            delimiter="\t",
            header=0,
            usecols=[
                "Experimental System", "Experimental System Type",
                "Throughput", "SWISS-PROT Accessions Interactor A",
                "SWISS-PROT Accessions Interactor B"
            ],
    ):
        if (row["SWISS-PROT Accessions Interactor A"] == "-"
                or row["SWISS-PROT Accessions Interactor B"] == "-"):
            continue

        if ((not experimental_system
             or row["Experimental System"] in experimental_system) and
            (not experimental_system_type
             or row["Experimental System Type"] in experimental_system_type)
                and (not interaction_throughput
                     or any(it in interaction_throughput
                            for it in row["Throughput"].split("|")))):
            for interactor_a in row[
                    "SWISS-PROT Accessions Interactor A"].split("|"):

                if "-" in interactor_a and not interactor_a.split(
                        "-")[1].isnumeric():
                    interactor_a = interactor_a.split("-")[0]

                for interactor_b in row[
                        "SWISS-PROT Accessions Interactor B"].split("|"):

                    if "-" in interactor_b and not interactor_b.split(
                            "-")[1].isnumeric():
                        interactor_b = interactor_b.split("-")[0]

                    for primary_interactor_a in primary_accession.get(
                            interactor_a, {interactor_a}):
                        for primary_interactor_b in primary_accession.get(
                                interactor_b, {interactor_b}):
                            yield (primary_interactor_a, primary_interactor_b)
