import math
import statistics
import bisect
import json

import networkx as nx
import pandas as pd

from pipeline.configuration import data
from pipeline.utilities import fetch
from pipeline.utilities import mitab


class ProteinProteinInteractionNetwork(nx.Graph):
    def __init__(self):
        super(ProteinProteinInteractionNetwork, self).__init__()

    def add_proteins_from_excel(
        self,
        file_name,
        ptm,
        time,
        protein_accession_col,
        position_col,
        replicates,
        protein_accession_format,
        position_format,
        sheet_name=0,
        header=0,
        num_sites=1,
        num_replicates=1,
        merge_replicates=statistics.mean,
        convert_measurement=math.log2,
    ):
        proteins = {}
        for _, row in pd.read_excel(
            file_name,
            sheet_name=sheet_name,
            header=header,
            usecols=[protein_accession_col, position_col] + replicates,
            dtype={
                protein_accession_col: str,
                position_col: str,
                **{replicate: float for replicate in replicates},
            },
        ).iterrows():

            if pd.isna(row[protein_accession_col]) or pd.isna(row[position_col]):
                continue

            measurements = [row[repl] for repl in replicates if not pd.isna(row[repl])]

            if len(measurements) >= min(num_replicates, len(replicates)):
                protein_accessions = [
                    str(protein_accession)
                    for protein_accession in protein_accession_format(
                        row[protein_accession_col]
                    )
                ]
                positions = [
                    int(position) for position in position_format(row[position_col])
                ]

                if len(protein_accessions) == len(positions):
                    for protein_accession, position in zip(
                        protein_accessions, positions
                    ):
                        if len(protein_accession.split("-")) > 1:
                            protein, isoform = protein_accession.split("-")
                        else:
                            protein, isoform = protein_accession, "1"

                        if protein not in proteins:
                            proteins[protein] = {}
                        if isoform not in proteins[protein]:
                            proteins[protein][isoform] = []

                        bisect.insort(
                            proteins[protein][isoform],
                            (
                                position,
                                convert_measurement(merge_replicates(measurements)),
                            ),
                        )
                else:
                    for protein_accession in protein_accessions:
                        if len(protein_accession.split("-")) > 1:
                            protein, isoform = protein_accession.split("-")
                        else:
                            protein, isoform = protein_accession, "1"

                        if protein not in proteins:
                            proteins[protein] = {}
                        if isoform not in proteins[protein]:
                            proteins[protein][isoform] = []

                        proteins[protein][isoform].append(
                            (0, convert_measurement(merge_replicates(measurements)))
                        )

        reviewed_proteins, primary_accession = {}, {}
        for line in fetch.iterate_data(data.UNIPROT_SWISS_PROT):
            if line.split("   ")[0] == "AC":
                accessions = line.split("   ")[1].rstrip(";").split("; ")
                for i, accession in enumerate(accessions):
                    if accession in proteins:
                        reviewed_proteins[accession] = proteins[accession]
                        if i > 0:
                            primary_accession[accession] = accessions[0]
        proteins = reviewed_proteins

        for protein in primary_accession:
            if primary_accession[protein] not in proteins:
                proteins[primary_accession[protein]] = proteins.pop(protein)

        for protein in proteins:
            for isoform in proteins[protein]:
                if isoform != "1":
                    self.add_node("{}-{}".format(protein, isoform))
                else:
                    self.add_node(protein)

                if len(proteins[protein][isoform]) > num_sites:
                    proteins[protein][isoform] = sorted(
                        sorted(
                            proteins[protein][isoform],
                            key=lambda tp: tp[1],
                            reverse=True,
                        )[:num_sites]
                    )
                for i in range(len(proteins[protein][isoform])):
                    if isoform != "1":
                        self.nodes["{}-{}".format(protein, isoform)][
                            "{} {} {}".format(str(time), ptm, str(i + 1))
                        ] = proteins[protein][isoform][i][1]
                    else:
                        self.nodes[protein][
                            "{} {} {}".format(str(time), ptm, str(i + 1))
                        ] = proteins[protein][isoform][i][1]

                yield (
                    "{}-{}".format(protein, isoform) if isoform != "1" else protein,
                    tuple(
                        [
                            proteins[protein][isoform][i][1]
                            for i in range(len(proteins[protein][isoform]))
                        ]
                    ),
                )

    def get_times(self):
        return tuple(
            sorted(
                set(
                    int(attr.split(" ")[0])
                    for protein in self
                    for attr in self.nodes[protein]
                    if len(attr.split(" ")) == 3
                )
            )
        )

    def get_post_translational_modifications(self):
        return {
            time: tuple(
                sorted(
                    set(
                        attr.split(" ")[1]
                        for protein in self
                        for attr in self.nodes[protein]
                        if len(attr.split(" ")) == 3 and attr.split(" ")[0] == str(time)
                    )
                )
            )
            for time in self.get_times()
        }

    def get_sites(self):
        return {
            time: {
                ptm: max(
                    int(attr.split(" ")[2])
                    for protein in self
                    for attr in self.nodes[protein]
                    if len(attr.split(" ")) == 3
                    and attr.split(" ")[0] == str(time)
                    and attr.split(" ")[1] == ptm
                )
                for ptm in self.get_post_translational_modifications()[time]
            }
            for time in self.get_times()
        }

    def set_ptm_data_column(self):
        for time in self.get_times():
            for protein in self:
                self.nodes[protein]["PTM {}".format(time)] = " ".join(
                    tuple(
                        sorted(
                            set(
                                attr.split(" ")[1]
                                for attr in self.nodes[protein]
                                if len(attr.split(" ")) == 3
                                and attr.split(" ")[0] == str(time)
                            )
                        )
                    )
                )

    def set_trend_data_column(
        self, merge_trends=statistics.mean, mid_range=(-1.0, 1.0)
    ):
        modifications = self.get_post_translational_modifications()
        for time in self.get_times():
            for protein in self:
                ptm = {}
                for post_translational_modification in modifications[time]:
                    trends = [
                        self.nodes[protein][attr]
                        for attr in self.nodes[protein]
                        if len(attr.split(" ")) == 3
                        and attr.split(" ")[0] == str(time)
                        and attr.split(" ")[1] == post_translational_modification
                    ]
                    if trends:
                        ptm[post_translational_modification] = merge_trends(trends)

                if ptm:
                    if all(trend > 0.0 for trend in ptm.values()):
                        if any(trend >= mid_range[1] for trend in ptm.values()):
                            self.nodes[protein]["trend {}".format(time)] = "up"
                        else:
                            self.nodes[protein]["trend {}".format(time)] = "mid up"
                    elif all(trend < 0.0 for trend in ptm.values()):
                        if any(trend <= mid_range[0] for trend in ptm.values()):
                            self.nodes[protein]["trend {}".format(time)] = "down"
                        else:
                            self.nodes[protein]["trend {}".format(time)] = "mid down"
                    else:
                        self.nodes[protein]["trend {}".format(time)] = " ".join(
                            sorted(
                                [
                                    "{} up".format(post_translational_modification)
                                    if ptm[post_translational_modification] > 0.0
                                    else "{} down".format(
                                        post_translational_modification
                                    )
                                    for post_translational_modification in ptm
                                ]
                            )
                        )
                else:
                    self.nodes[protein]["trend {}".format(time)] = ""

    def add_interactions_from_BioGRID(
        self, experimental_system=[], multi_validated_physical=False
    ):
        uniprot = {}
        for row in fetch.iterate_tabular_data(
            data.UNIPROT_ID_MAP,
            delimiter="\t",
            usecols=[0, 1, 2],
        ):
            if row[1] == "BioGRID" and row[0] in self.nodes:
                uniprot[int(row[2])] = row[0]

        for row in fetch.iterate_tabular_data(
            data.BIOGRID_ID_MAP_ARCHIVE,
            zip_file=data.BIOGRID_ID_MAP_FILE,
            delimiter="\t",
            header=20,
            usecols=[
                "BIOGRID_ID",
                "IDENTIFIER_VALUE",
                "IDENTIFIER_TYPE",
                "ORGANISM_OFFICIAL_NAME",
            ],
        ):
            if (
                row["IDENTIFIER_TYPE"] in ("UNIPROT-ACCESSION", "UNIPROT-ISOFORM")
                and row["ORGANISM_OFFICIAL_NAME"] == "Homo sapiens"
                and row["IDENTIFIER_VALUE"] in self.nodes
            ):
                uniprot[int(row["BIOGRID_ID"])] = row["IDENTIFIER_VALUE"]

        for row in fetch.iterate_tabular_data(
            data.BIOGRID_MV_PHYSICAL_ARCHIVE
            if multi_validated_physical
            else data.BIOGRID_ARCHIVE,
            zip_file=data.BIOGRID_MV_PHYSICAL_FILE
            if multi_validated_physical
            else data.BIOGRID_FILE,
            delimiter="\t",
            header=0,
            usecols=[
                "BioGRID ID Interactor A",
                "BioGRID ID Interactor B",
                "Experimental System",
                "Experimental System Type",
                "Organism ID Interactor A",
                "Organism ID Interactor B",
                "Throughput",
            ],
        ):
            if (
                uniprot.get(row["BioGRID ID Interactor A"])
                and uniprot.get(row["BioGRID ID Interactor B"])
                and uniprot[row["BioGRID ID Interactor A"]]
                != uniprot[row["BioGRID ID Interactor B"]]
                and (
                    not experimental_system
                    or row["Experimental System"] in experimental_system
                )
                and row["Experimental System Type"] == "physical"
                and row["Organism ID Interactor A"] == 9606
                and row["Organism ID Interactor B"] == 9606
            ):
                self.add_edge(
                    uniprot[row["BioGRID ID Interactor A"]],
                    uniprot[row["BioGRID ID Interactor B"]],
                )
                self.edges[
                    uniprot[row["BioGRID ID Interactor A"]],
                    uniprot[row["BioGRID ID Interactor B"]],
                ]["BioGRID"] = 1.0

                yield (
                    uniprot[row["BioGRID ID Interactor A"]],
                    uniprot[row["BioGRID ID Interactor B"]],
                )

    def add_interactions_from_IntAct(
        self, interaction_detection_methods=[], interaction_types=[], mi_score=0.0
    ):
        for row in fetch.iterate_tabular_data(
            data.INTACT_ARCHIVE,
            zip_file=data.INTACT_FILE,
            delimiter="\t",
            header=0,
            usecols=[
                "#ID(s) interactor A",
                "ID(s) interactor B",
                "Alt. ID(s) interactor A",
                "Alt. ID(s) interactor B",
                "Taxid interactor A",
                "Taxid interactor B",
                "Interaction detection method(s)",
                "Interaction type(s)",
                "Confidence value(s)",
            ],
        ):

            if not (
                interactor_a := mitab.get_id_from_ns(
                    row["#ID(s) interactor A"], "uniprotkb"
                )
            ):
                if not (
                    interactor_a := mitab.get_id_from_ns(
                        row["Alt. ID(s) interactor A"], "uniprotkb"
                    )
                ):
                    continue
            if interactor_a not in self:
                continue

            if not (
                interactor_b := mitab.get_id_from_ns(
                    row["ID(s) interactor B"], "uniprotkb"
                )
            ):
                if not (
                    interactor_b := mitab.get_id_from_ns(
                        row["Alt. ID(s) interactor B"], "uniprotkb"
                    )
                ):
                    continue
            if interactor_b not in self:
                continue

            if interactor_a == interactor_b:
                continue

            if not (
                mitab.ns_has_id(row["Taxid interactor A"], "taxid", "9606")
                and mitab.ns_has_id(row["Taxid interactor B"], "taxid", "9606")
            ):
                continue

            if not (
                not interaction_detection_methods
                or mitab.ns_has_any_term(
                    row["Interaction detection method(s)"],
                    "psi-mi",
                    interaction_detection_methods,
                )
            ):
                continue

            if not (
                not interaction_types
                or mitab.ns_has_any_term(
                    row["Interaction type(s)"], "psi-mi", interaction_types
                )
            ):
                continue

            if score := mitab.get_id_from_ns(
                row["Confidence value(s)"], "intact-miscore"
            ):
                score = float(score)
                if score < mi_score:
                    continue
            else:
                continue

            if self.has_edge(interactor_a, interactor_b):
                self.edges[interactor_a, interactor_b]["IntAct"] = max(
                    score, self.edges[interactor_a, interactor_b].get("IntAct", 0.0)
                )
            else:
                self.add_edge(interactor_a, interactor_b)
                self.edges[interactor_a, interactor_b]["IntAct"] = score

            yield (
                interactor_a,
                interactor_b,
                self.edges[interactor_a, interactor_b]["IntAct"],
            )

    def add_interactions_from_STRING(
        self,
        neighborhood=0.0,
        neighborhood_transferred=0.0,
        fusion=0.0,
        cooccurence=0.0,
        homology=0.0,
        coexpression=0.0,
        coexpression_transferred=0.0,
        experiments=0.0,
        experiments_transferred=0.0,
        database=0.0,
        database_transferred=0.0,
        textmining=0.0,
        textmining_transferred=0.0,
        combined_score=0.0,
        physical=False,
    ):

        uniprot = {}
        for row in fetch.iterate_tabular_data(
            data.UNIPROT_ID_MAP,
            delimiter="\t",
            usecols=[0, 1, 2],
        ):
            if row[1] == "STRING" and row[0] in self.nodes:
                uniprot[row[2]] = row[0]

        for row in fetch.iterate_tabular_data(data.STRING_ID_MAP, usecols=[1, 2]):
            if row[1].split("|")[0] in self.nodes:
                uniprot[row[2]] = row[1].split("|")[0]

        thresholds = {
            column: threshold
            for column, threshold in {
                "neighborhood": neighborhood,
                "neighborhood_transferred": neighborhood_transferred,
                "fusion": fusion,
                "cooccurence": cooccurence,
                "homology": homology,
                "coexpression": coexpression,
                "coexpression_transferred": coexpression_transferred,
                "experiments": experiments,
                "experiments_transferred": experiments_transferred,
                "database": database,
                "database_transferred": database_transferred,
                "textmining": textmining,
                "textmining_transferred": textmining_transferred,
            }.items()
            if threshold
        }
        thresholds["combined_score"] = combined_score

        for row in fetch.iterate_tabular_data(
            data.STRING_PHYSICAL if physical else data.STRING,
            delimiter=" ",
            header=0,
            usecols=["protein1", "protein2"] + list(thresholds.keys()),
        ):
            if (
                uniprot.get(row["protein1"])
                and uniprot.get(row["protein2"])
                and uniprot[row["protein1"]] != uniprot[row["protein2"]]
                and all(
                    row[column] / 1000 >= thresholds[column] for column in thresholds
                )
            ):
                if self.has_edge(uniprot[row["protein1"]], uniprot[row["protein2"]]):
                    self.edges[uniprot[row["protein1"]], uniprot[row["protein2"]]][
                        "STRING"
                    ] = max(
                        row["combined_score"] / 1000,
                        self.edges[
                            uniprot[row["protein1"]], uniprot[row["protein2"]]
                        ].get("STRING", 0.0),
                    )
                else:
                    self.add_edge(uniprot[row["protein1"]], uniprot[row["protein2"]])
                    self.edges[uniprot[row["protein1"]], uniprot[row["protein2"]]][
                        "STRING"
                    ] = (row["combined_score"] / 1000)

                yield (
                    uniprot[row["protein1"]],
                    uniprot[row["protein2"]],
                    self.edges[uniprot[row["protein1"]], uniprot[row["protein2"]]][
                        "STRING"
                    ],
                )
