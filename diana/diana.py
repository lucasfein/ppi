"""
DIANA: data integration and network analysis for post-translational modification
mass spectrometry data
"""
import argparse
import concurrent.futures
import csv
import json
import os
import re
from typing import Any, Mapping

import networkx as nx

from cytoscape import (gene_ontology_network_style,
                       protein_interaction_network_style,
                       reactome_network_style)
from databases import gene_ontology, reactome
from interface import (average, score, correction, default, modularization,
                       prioritization, test)
from networks import (gene_ontology_network, protein_interaction_network,
                      reactome_network)


def process_workflow(identifier: str, configuration: Mapping[str, Any]) -> None:
    """
    Executes a workflow with identifier specified in configuration.

    Args:
        identifier: An identifier for the workflow.
        configuration: The specification of a workflow.
    """
    network = protein_interaction_network.get_network()

    for entry in configuration.get("proteins", {}):
        if ("file" in entry and "accession column" in entry and
                "replicate columns" in entry):
            if "position column" in entry:
                protein_interaction_network.add_sites_from_table(
                    network,
                    file_name=entry["file"],
                    protein_accession_column=entry["accession column"],
                    protein_accession_format=re.compile(
                        entry.get("accession format", "^(.+?)$")),
                    position_column=entry["position column"],
                    position_format=re.compile(
                        entry.get("position format", "^(.+?)$")),
                    replicate_columns=entry["replicate columns"],
                    replicate_format=re.compile(
                        entry.get("replicate format", "^(.+?)$")),
                    sheet_name=entry.get("sheet", 1) - 1 if isinstance(
                        entry.get("sheet", 1), int) else entry["sheet"],
                    header=entry.get("header", 1) - 1,
                    time=entry["time"] if entry.get("time") and
                    isinstance(entry["time"], int) else 0,
                    modification=entry["PTM"].replace(" ", "")
                    if entry.get("PTM") else "PTM",
                    number_sites=entry.get("sites", 5),
                    number_replicates=entry.get("replicates", 1),
                    replicate_average=average.REPLICATE_AVERAGE[entry.get(
                        "replicate average", "mean")],
                    measurement_score=score.LOGARITHM[entry.get("logarithm")],
                    site_prioritization=prioritization.SITE_PRIORITIZATION[
                        entry.get("site prioritization", "absolute")])
            else:
                protein_interaction_network.add_proteins_from_table(
                    network,
                    file_name=entry["file"],
                    protein_accession_column=entry["accession column"],
                    protein_accession_format=re.compile(
                        entry.get("accession format", "^(.+?)$")),
                    replicate_columns=entry["replicate columns"],
                    replicate_format=re.compile(
                        entry.get("replicate format", "^(.+?)$")),
                    sheet_name=entry.get("sheet", 1) - 1 if isinstance(
                        entry.get("sheet", 1), int) else entry["sheet"],
                    header=entry.get("header", 1) - 1,
                    time=entry["time"] if entry.get("time") and
                    isinstance(entry["time"], int) else 0,
                    modification=entry["PTM"].replace(" ", "")
                    if entry.get("PTM") else "PTM",
                    number_replicates=entry.get("replicates", 1),
                    measurement_score=score.LOGARITHM[entry.get("logarithm")])

        elif "accessions" in entry:
            network.add_nodes_from(entry["accessions"])

    for entry in configuration.get("networks", {}):
        network = nx.compose(
            network,
            nx.readwrite.graphml.read_graphml(entry["network"]) if
            entry.get("network") else protein_interaction_network.get_network())

    nodes_to_remove = set(network.nodes())
    for organism in set(
            entry.get("organism", 9606)
            for entry in configuration.get("proteins", {})) | set(
                entry.get("organism", 9606)
                for entry in configuration.get("networks", {})):
        nodes_to_remove.intersection_update(
            protein_interaction_network.map_proteins(network, organism))
    network.remove_nodes_from(nodes_to_remove)

    if "protein-protein interactions" in configuration:
        for neighbors in range(
                max(configuration["protein-protein interactions"].get(
                    database, {}).get("neighbors", 0) for database in
                    configuration["protein-protein interactions"])):
            interacting_proteins = set()

            if "BioGRID" in configuration[
                    "protein-protein interactions"] and configuration[
                        "protein-protein interactions"]["BioGRID"].get(
                            "neighbors", 0) > neighbors:
                interacting_proteins.update(
                    protein_interaction_network.get_neighbors_from_biogrid(
                        network,
                        interaction_throughput=configuration[
                            "protein-protein interactions"]["BioGRID"].get(
                                "interaction throughput", []),
                        experimental_system=configuration[
                            "protein-protein interactions"]["BioGRID"].get(
                                "experimental system", []),
                        experimental_system_type=configuration[
                            "protein-protein interactions"]["BioGRID"].get(
                                "experimental system type", []),
                        multi_validated_physical=configuration[
                            "protein-protein interactions"]["BioGRID"].get(
                                "multi-validated physical", False),
                        organism=configuration["protein-protein interactions"]
                        ["BioGRID"].get("organism", 9606),
                        version=configuration["protein-protein interactions"]
                        ["BioGRID"].get("version")))

            if "CORUM" in configuration[
                    "protein-protein interactions"] and configuration[
                        "protein-protein interactions"]["CORUM"].get(
                            "neighbors", 0) > neighbors:
                interacting_proteins.update(
                    protein_interaction_network.get_neighbors_from_corum(
                        network,
                        purification_methods=configuration[
                            "protein-protein interactions"]["CORUM"].get(
                                "purification methods", [])))

            if "IntAct" in configuration[
                    "protein-protein interactions"] and configuration[
                        "protein-protein interactions"]["IntAct"].get(
                            "neighbors", 0) > neighbors:
                interacting_proteins.update(
                    protein_interaction_network.get_neighbors_from_intact(
                        network,
                        interaction_detection_methods=configuration[
                            "protein-protein interactions"]["IntAct"].get(
                                "interaction detection methods", []),
                        interaction_types=configuration[
                            "protein-protein interactions"]["IntAct"].get(
                                "interaction types", []),
                        psi_mi_score=configuration[
                            "protein-protein interactions"]["IntAct"].get(
                                "score", 0.0),
                        organism=configuration["protein-protein interactions"]
                        ["IntAct"].get("organism", 9606),
                    ))

            if "MINT" in configuration[
                    "protein-protein interactions"] and configuration[
                        "protein-protein interactions"]["MINT"].get(
                            "neighbors", 0) > neighbors:
                interacting_proteins.update(
                    protein_interaction_network.get_neighbors_from_mint(
                        network,
                        interaction_detection_methods=configuration[
                            "protein-protein interactions"]["MINT"].get(
                                "interaction detection methods", []),
                        interaction_types=configuration[
                            "protein-protein interactions"]["MINT"].get(
                                "interaction types", []),
                        psi_mi_score=configuration[
                            "protein-protein interactions"]["MINT"].get(
                                "score", 0.0),
                        organism=configuration["protein-protein interactions"]
                        ["MINT"].get("organism", 9606),
                    ))

            if "Reactome" in configuration[
                    "protein-protein interactions"] and configuration[
                        "protein-protein interactions"]["Reactome"].get(
                            "neighbors", 0) > neighbors:
                interacting_proteins.update(
                    protein_interaction_network.get_neighbors_from_reactome(
                        network,
                        interaction_context=configuration[
                            "protein-protein interactions"]["Reactome"].get(
                                "interaction context", []),
                        interaction_type=configuration[
                            "protein-protein interactions"]["Reactome"].get(
                                "interaction type", []),
                        organism=configuration["protein-protein interactions"]
                        ["Reactome"].get("organism", 9606),
                    ))

            if "STRING" in configuration[
                    "protein-protein interactions"] and configuration[
                        "protein-protein interactions"]["STRING"].get(
                            "neighbors", 0) > neighbors:
                interacting_proteins.update(
                    protein_interaction_network.get_neighbors_from_string(
                        network,
                        neighborhood=configuration[
                            "protein-protein interactions"]["STRING"].get(
                                "neighborhood score", 0.0),
                        neighborhood_transferred=configuration[
                            "protein-protein interactions"]["STRING"].get(
                                "neighborhood transferred score", 0.0),
                        fusion=configuration["protein-protein interactions"]
                        ["STRING"].get("fusion score", 0.0),
                        cooccurence=configuration[
                            "protein-protein interactions"]["STRING"].get(
                                "cooccurence score", 0.0),
                        homology=configuration["protein-protein interactions"]
                        ["STRING"].get("homology score", 0.0),
                        coexpression=configuration[
                            "protein-protein interactions"]["STRING"].get(
                                "coexpression score", 0.0),
                        coexpression_transferred=configuration[
                            "protein-protein interactions"]["STRING"].get(
                                "coexpression transferred score", 0.0),
                        experiments=configuration[
                            "protein-protein interactions"]["STRING"].get(
                                "experiments score", 0.0),
                        experiments_transferred=configuration[
                            "protein-protein interactions"]["STRING"].get(
                                "experiments transferred score", 0.0),
                        database=configuration["protein-protein interactions"]
                        ["STRING"].get("database score", 0.0),
                        database_transferred=configuration[
                            "protein-protein interactions"]["STRING"].get(
                                "database transferred score", 0.0),
                        textmining=configuration["protein-protein interactions"]
                        ["STRING"].get("textmining score", 0.0),
                        textmining_transferred=configuration[
                            "protein-protein interactions"]["STRING"].get(
                                "textmining transferred score", 0.0),
                        combined_score=configuration[
                            "protein-protein interactions"]["STRING"].get(
                                "combined score", 0.0),
                        physical=configuration["protein-protein interactions"]
                        ["STRING"].get("physical", False),
                        organism=configuration["protein-protein interactions"]
                        ["STRING"].get("organism", 9606),
                        version=configuration["protein-protein interactions"]
                        ["STRING"].get("version", 11.5),
                    ))

            network.add_nodes_from(interacting_proteins)
            nodes_to_remove = set(network.nodes())
            for organism in set(configuration["protein-protein interactions"]
                                [database].get("organism", 9606) for database in
                                configuration["protein-protein interactions"]):
                nodes_to_remove.intersection_update(
                    protein_interaction_network.map_proteins(network, organism))
            network.remove_nodes_from(nodes_to_remove)

        if "BioGRID" in configuration["protein-protein interactions"]:
            protein_interaction_network.add_protein_interactions_from_biogrid(
                network,
                interaction_throughput=configuration[
                    "protein-protein interactions"]["BioGRID"].get(
                        "interaction throughput", []),
                experimental_system=configuration[
                    "protein-protein interactions"]["BioGRID"].get(
                        "experimental system", []),
                experimental_system_type=configuration[
                    "protein-protein interactions"]["BioGRID"].get(
                        "experimental system type", []),
                multi_validated_physical=configuration[
                    "protein-protein interactions"]["BioGRID"].get(
                        "multi-validated physical", False),
                organism=configuration["protein-protein interactions"]
                ["BioGRID"].get("organism", 9606),
                version=configuration["protein-protein interactions"]
                ["BioGRID"].get("version"))

        if "CORUM" in configuration["protein-protein interactions"]:
            protein_interaction_network.add_protein_interactions_from_corum(
                network,
                purification_methods=configuration[
                    "protein-protein interactions"]["CORUM"].get(
                        "purification methods", []))

        if "IntAct" in configuration["protein-protein interactions"]:
            protein_interaction_network.add_protein_interactions_from_intact(
                network,
                interaction_detection_methods=configuration[
                    "protein-protein interactions"]["IntAct"].get(
                        "interaction detection methods", []),
                interaction_types=configuration["protein-protein interactions"]
                ["IntAct"].get("interaction types", []),
                psi_mi_score=configuration["protein-protein interactions"]
                ["IntAct"].get("score", 0.0),
                organism=configuration["protein-protein interactions"]
                ["IntAct"].get("organism", 9606),
            )

        if "MINT" in configuration["protein-protein interactions"]:
            protein_interaction_network.add_protein_interactions_from_mint(
                network,
                interaction_detection_methods=configuration[
                    "protein-protein interactions"]["MINT"].get(
                        "interaction detection methods", []),
                interaction_types=configuration["protein-protein interactions"]
                ["MINT"].get("interaction types", []),
                psi_mi_score=configuration["protein-protein interactions"]
                ["MINT"].get("score", 0.0),
                organism=configuration["protein-protein interactions"]
                ["MINT"].get("organism", 9606),
            )

        if "Reactome" in configuration["protein-protein interactions"]:
            protein_interaction_network.add_protein_interactions_from_reactome(
                network,
                interaction_context=configuration[
                    "protein-protein interactions"]["Reactome"].get(
                        "interaction context", []),
                interaction_type=configuration["protein-protein interactions"]
                ["Reactome"].get("interaction type", []),
                organism=configuration["protein-protein interactions"]
                ["Reactome"].get("organism", 9606),
            )

        if "STRING" in configuration["protein-protein interactions"]:
            protein_interaction_network.add_protein_interactions_from_string(
                network,
                neighborhood=configuration["protein-protein interactions"]
                ["STRING"].get("neighborhood score", 0.0),
                neighborhood_transferred=configuration[
                    "protein-protein interactions"]["STRING"].get(
                        "neighborhood transferred score", 0.0),
                fusion=configuration["protein-protein interactions"]
                ["STRING"].get("fusion score", 0.0),
                cooccurence=configuration["protein-protein interactions"]
                ["STRING"].get("cooccurence score", 0.0),
                homology=configuration["protein-protein interactions"]
                ["STRING"].get("homology score", 0.0),
                coexpression=configuration["protein-protein interactions"]
                ["STRING"].get("coexpression score", 0.0),
                coexpression_transferred=configuration[
                    "protein-protein interactions"]["STRING"].get(
                        "coexpression transferred score", 0.0),
                experiments=configuration["protein-protein interactions"]
                ["STRING"].get("experiments score", 0.0),
                experiments_transferred=configuration[
                    "protein-protein interactions"]["STRING"].get(
                        "experiments transferred score", 0.0),
                database=configuration["protein-protein interactions"]
                ["STRING"].get("database score", 0.0),
                database_transferred=configuration[
                    "protein-protein interactions"]["STRING"].get(
                        "database transferred score", 0.0),
                textmining=configuration["protein-protein interactions"]
                ["STRING"].get("textmining score", 0.0),
                textmining_transferred=configuration[
                    "protein-protein interactions"]["STRING"].get(
                        "textmining transferred score", 0.0),
                combined_score=configuration["protein-protein interactions"]
                ["STRING"].get("combined score", 0.0),
                physical=configuration["protein-protein interactions"]
                ["STRING"].get("physical", False),
                organism=configuration["protein-protein interactions"]
                ["STRING"].get("organism", 9606),
                version=configuration["protein-protein interactions"]
                ["STRING"].get("version", 11.5),
            )

        if any(
                protein_interaction_network.get_modifications(network, time)
                for time in protein_interaction_network.get_times(network)):

            if "Cytoscape" in configuration:
                measurements = {
                    modification: default.MEASUREMENT_RANGE.get(
                        score, default.MEASUREMENT_RANGE[None])
                    for modification, score in configuration["Cytoscape"].get(
                        "node color", {}).get("score", {}).items()
                }

                for modification, measurement_range in configuration[
                        "Cytoscape"].get("node color",
                                         {}).get("measurement", {}).items():
                    measurements[modification] = measurement_range

                protein_interaction_network.set_measurements(
                    network,
                    site_average={
                        modification: average.SITE_AVERAGE.get(
                            site_average,
                            average.SITE_AVERAGE["maximum absolute logarithm"])
                        for modification,
                        site_average in configuration["Cytoscape"].get(
                            "site average", {}).items()
                    },
                    replicate_average={
                        modification: average.REPLICATE_AVERAGE.get(
                            replicate_average,
                            average.REPLICATE_AVERAGE["mean"]) for modification,
                        replicate_average in configuration["Cytoscape"].get(
                            "replicate average", {}).items()
                    },
                    measurements=measurements,
                    measurement_score={
                        modification: score.MEASUREMENT_SCORE.get(
                            measurement_score, score.MEASUREMENT_SCORE[None])
                        for modification, measurement_score in
                        configuration["Cytoscape"].get("score", {})
                    })

                protein_interaction_network.set_edge_weights(
                    network,
                    weight=average.CONFIDENCE_SCORE_AVERAGE[
                        configuration["Cytoscape"].get("edge transparency")],
                    attribute="score")

                styles = protein_interaction_network_style.get_styles(
                    network,
                    node_shape_modifications=configuration["Cytoscape"].get(
                        "node shape", {}).get("PTMs", []),
                    node_color_modifications=configuration["Cytoscape"].get(
                        "node color", {}).get("PTMs", []),
                    node_size_modification=configuration["Cytoscape"].get(
                        "node size", {}).get("PTM", None),
                    bar_chart_modifications=configuration["Cytoscape"].get(
                        "bar chart", {}).get("PTMs", []),
                    measurement_score={
                        modification: score.MEASUREMENT_SCORE.get(
                            measurement_score, score.MEASUREMENT_SCORE[None])
                        for modification, measurement_score in
                        configuration["Cytoscape"].get("score", {})
                    },
                    site_average={
                        modification: average.SITE_AVERAGE.get(
                            site_average,
                            average.SITE_AVERAGE["maximum absolute logarithm"])
                        for modification,
                        site_average in configuration["Cytoscape"].get(
                            "site average", {}).items()
                    },
                    replicate_average={
                        modification: average.REPLICATE_AVERAGE.get(
                            replicate_average,
                            average.REPLICATE_AVERAGE["mean"]) for modification,
                        replicate_average in configuration["Cytoscape"].get(
                            "replicate average", {}).items()
                    },
                    confidence_score_average=average.CONFIDENCE_SCORE_AVERAGE[
                        configuration["Cytoscape"].get("edge transparency")])

                protein_interaction_network_style.export(styles, identifier)

        protein_interaction_network.export(network, identifier)

    if "Gene Ontology network" in configuration:
        if "PTMs" in configuration["Gene Ontology network"]:
            if configuration["Gene Ontology network"].get(
                    "intersection", False):
                proteins = set(network.nodes())
            else:
                proteins = set()

            for time in protein_interaction_network.get_times(network):
                for m in configuration["Gene Ontology network"].get("PTMs", []):
                    if m in protein_interaction_network.get_modifications(
                            network, time):
                        measurement_range = (
                            score.MEASUREMENT_SCORE[
                                configuration["Gene Ontology network"].get(
                                    "score", {}).get(m)]
                            (configuration["Gene Ontology network"].get(
                                "measurement", default.MEASUREMENT_RANGE[
                                    configuration["Gene Ontology network"].get(
                                        "score", {}).get(m)])[0],
                             protein_interaction_network.get_measurements(
                                 network, time, m, average.SITE_AVERAGE[
                                     configuration["Gene Ontology network"].get(
                                         "site average",
                                         {}).get(m,
                                                 "maximum absolute logarithm")],
                                 average.REPLICATE_AVERAGE[
                                     configuration["Gene Ontology network"].get(
                                         "replicate average",
                                         {}).get(m, "mean")])),
                            score.MEASUREMENT_SCORE[
                                configuration["Gene Ontology network"].get(
                                    "score", {}).get(m)]
                            (configuration["Gene Ontology network"].get(
                                "measurement", default.MEASUREMENT_RANGE[
                                    configuration["Gene Ontology network"].get(
                                        "score", {}).get(m)])[1],
                             protein_interaction_network.get_measurements(
                                 network, time, m, average.SITE_AVERAGE[
                                     configuration["Gene Ontology network"].get(
                                         "site average",
                                         {}).get(m,
                                                 "maximum absolute logarithm")],
                                 average.REPLICATE_AVERAGE[
                                     configuration["Gene Ontology network"].get(
                                         "replicate average",
                                         {}).get(m, "mean")])))

                        if configuration["Gene Ontology network"].get(
                                "intersection", False):
                            proteins.intersection_update(
                                protein_interaction_network.get_proteins(
                                    network, time, m,
                                    average.SITE_AVERAGE[configuration[
                                        "Gene Ontology network"].get(
                                            "site average", {}).get(
                                                m,
                                                "maximum absolute logarithm")],
                                    average.REPLICATE_AVERAGE[configuration[
                                        "Gene Ontology network"].get(
                                            "replicate average",
                                            {}).get(m, "mean")],
                                    measurement_range))

                        else:
                            proteins.update(
                                protein_interaction_network.get_proteins(
                                    network, time, m,
                                    average.SITE_AVERAGE[configuration[
                                        "Gene Ontology network"].get(
                                            "site average", {}).get(
                                                m,
                                                "maximum absolute logarithm")],
                                    average.REPLICATE_AVERAGE[configuration[
                                        "Gene Ontology network"].get(
                                            "replicate average",
                                            {}).get(m, "mean")],
                                    measurement_range))

            ontology_network = gene_ontology_network.get_network(
                proteins,
                reference=network.nodes()
                if not configuration["Gene Ontology network"].get(
                    "annotation", False) else [],
                namespaces=[
                    namespace.replace(" ", "_")
                    for namespace in configuration["Gene Ontology network"].get(
                        "namespaces", [
                            "cellular component", "molecular function",
                            "biological process"
                        ])
                ],
                enrichment_test=test.ENRICHMENT_TEST[(
                    configuration["Gene Ontology network"].get(
                        "test", "hypergeometric"),
                    configuration["Gene Ontology network"].get(
                        "increase", True))],
                multiple_testing_correction=correction.CORRECTION[
                    configuration["Gene Ontology network"].get(
                        "correction", "Benjamini-Yekutieli")],
                organism=configuration["Gene Ontology network"].get(
                    "organism", 9606))

        else:
            ontology_network = gene_ontology_network.get_network(
                network.nodes(),
                namespaces=[
                    namespace.replace(" ", "_")
                    for namespace in configuration["Gene Ontology network"].get(
                        "namespaces", [
                            "cellular component", "molecular function",
                            "biological process"
                        ])
                ],
                enrichment_test=test.ENRICHMENT_TEST[(
                    configuration["Gene Ontology network"].get(
                        "test", "hypergeometric"),
                    configuration["Gene Ontology network"].get(
                        "increase", True))],
                multiple_testing_correction=correction.CORRECTION[
                    configuration["Gene Ontology network"].get(
                        "correction", "Benjamini-Yekutieli")],
                organism=configuration["Gene Ontology network"].get(
                    "organism", 9606))

        gene_ontology_network.export(ontology_network,
                                     f"{identifier}_gene_ontology")

        if "Cytoscape" in configuration:
            ontology_network_styles = gene_ontology_network_style.get_styles(
                ontology_network)
            gene_ontology_network_style.export(ontology_network_styles,
                                               f"{identifier}_gene_ontology")

    if "Reactome network" in configuration:
        if "PTMs" in configuration["Reactome network"]:
            if configuration["Reactome network"].get("intersection", False):
                proteins = set(network.nodes())
            else:
                proteins = set()

            for time in protein_interaction_network.get_times(network):
                for m in configuration["Reactome network"].get("PTMs", []):
                    if m in protein_interaction_network.get_modifications(
                            network, time):
                        measurement_range = (
                            score.MEASUREMENT_SCORE[
                                configuration["Reactome network"].get(
                                    "score", {}).get(m)]
                            (configuration["Reactome network"].get(
                                "measurement", default.MEASUREMENT_RANGE[
                                    configuration["Reactome network"].get(
                                        "score", {}).get(m)])[0],
                             protein_interaction_network.get_measurements(
                                 network, time, m, average.SITE_AVERAGE[
                                     configuration["Reactome network"].get(
                                         "site average",
                                         {}).get(m,
                                                 "maximum absolute logarithm")],
                                 average.REPLICATE_AVERAGE[
                                     configuration["Reactome network"].get(
                                         "replicate average",
                                         {}).get(m,
                                                 "mean")])),
                            score.MEASUREMENT_SCORE[
                                configuration["Reactome network"].get(
                                    "score", {}).get(m)]
                            (configuration["Reactome network"].get(
                                "measurement", default.MEASUREMENT_RANGE[
                                    configuration["Reactome network"].get(
                                        "score", {}).get(m)])[1],
                             protein_interaction_network.get_measurements(
                                 network, time, m, average.SITE_AVERAGE[
                                     configuration["Reactome network"].get(
                                         "site average",
                                         {}).get(m,
                                                 "maximum absolute logarithm")],
                                 average.REPLICATE_AVERAGE[
                                     configuration["Reactome network"].get(
                                         "replicate average",
                                         {}).get(m, "mean")])))

                        if configuration["Reactome network"].get(
                                "intersection", False):
                            proteins.intersection_update(
                                protein_interaction_network.get_proteins(
                                    network, time, m, average.SITE_AVERAGE[
                                        configuration["Reactome network"].get(
                                            "site average", {}).get(
                                                m,
                                                "maximum absolute logarithm")],
                                    average.REPLICATE_AVERAGE[
                                        configuration["Reactome network"].get(
                                            "replicate average",
                                            {}).get(m, "mean")],
                                    measurement_range))

                        else:
                            proteins.update(
                                protein_interaction_network.get_proteins(
                                    network, time, m, average.SITE_AVERAGE[
                                        configuration["Reactome network"].get(
                                            "site average", {}).get(
                                                m,
                                                "maximum absolute logarithm")],
                                    average.REPLICATE_AVERAGE[
                                        configuration["Reactome network"].get(
                                            "replicate average",
                                            {}).get(m, "mean")],
                                    measurement_range))

            pathway_network = reactome_network.get_network(
                proteins,
                reference=network.nodes() if
                not configuration["Reactome network"].get("annotation", False)
                else [],
                enrichment_test=test.ENRICHMENT_TEST[(
                    configuration["Reactome network"].get(
                        "test", "hypergeometric"),
                    configuration["Reactome network"].get("increase", True))],
                multiple_testing_correction=correction.CORRECTION[
                    configuration["Reactome network"].get(
                        "correction", "Benjamini-Yekutieli")],
                organism=configuration["Reactome network"].get(
                    "organism", 9606))

        else:
            pathway_network = reactome_network.get_network(
                network.nodes(),
                enrichment_test=test.ENRICHMENT_TEST[(
                    configuration["Reactome network"].get(
                        "test", "hypergeometric"),
                    configuration["Reactome network"].get("increase", True))],
                multiple_testing_correction=correction.CORRECTION[
                    configuration["Reactome network"].get(
                        "correction", "Benjamini-Yekutieli")],
                organism=configuration["Reactome network"].get(
                    "organism", 9606))

        reactome_network.export(pathway_network, f"{identifier}_reactome")

        if "Cytoscape" in configuration:
            pathway_network_styles = reactome_network_style.get_styles(
                pathway_network)
            reactome_network_style.export(pathway_network_styles,
                                          f"{identifier}_reactome")

    if "community detection" in configuration:
        protein_interaction_network.set_edge_weights(
            network,
            weight=average.CONFIDENCE_SCORE_AVERAGE[
                configuration["community detection"].get("edge weight")])

        communities = protein_interaction_network.get_communities(
            network,
            community_size=configuration["community detection"].get(
                "community size", network.number_of_nodes()),
            community_size_average=average.MODULE_SIZE_AVERAGE[
                configuration["community detection"].get(
                    "community size average", "mean")],
            algorithm=modularization.ALGORITHM[
                configuration["community detection"].get(
                    "algorithm", "Louvain")],
            resolution=configuration["community detection"].get(
                "resolution", 1.0))

        protein_interaction_network.remove_edge_weights(network)

        export = {community: False for community in communities}

    if ("Gene Ontology enrichment" in configuration or
            "Gene Ontology enrichment" in configuration.get(
                "community detection", {})):
        with open(f"{identifier}_gene_ontology.tsv",
                  "w",
                  newline="",
                  encoding="utf-8") as gene_ontology_table:
            gene_ontology_writer = csv.writer(gene_ontology_table,
                                              dialect="excel-tab")
            gene_ontology_writer.writerow(
                ["network", "term", "name", "p-value"])

            if "PTMs" in configuration.get("Gene Ontology enrichment", {}):
                if configuration["Gene Ontology enrichment"].get(
                        "intersection", False):
                    proteins = set(network.nodes())
                else:
                    proteins = set()

                for time in protein_interaction_network.get_times(network):
                    for m in configuration["Gene Ontology enrichment"].get(
                            "PTMs", []):
                        if m in protein_interaction_network.get_modifications(
                                network, time):
                            measurement_range = (
                                score.MEASUREMENT_SCORE[configuration[
                                    "Gene Ontology enrichment"].get(
                                        "score", {}).get(m)]
                                (configuration["Gene Ontology enrichment"].get(
                                    "measurement",
                                    default.MEASUREMENT_RANGE[configuration[
                                        "Gene Ontology enrichment"].get(
                                            "score", {}).get(m)])[0],
                                 protein_interaction_network.get_measurements(
                                     network, time, m,
                                     average.SITE_AVERAGE[configuration[
                                         "Gene Ontology enrichment"].get(
                                             "site average", {}).get(
                                                 m,
                                                 "maximum absolute logarithm")],
                                     average.REPLICATE_AVERAGE[configuration[
                                         "Gene Ontology enrichment"].get(
                                             "replicate average",
                                             {}).get(m, "mean")])),
                                score.MEASUREMENT_SCORE[configuration[
                                    "Gene Ontology enrichment"].get(
                                        "score", {}).get(m)]
                                (configuration["Gene Ontology enrichment"].get(
                                    "measurement",
                                    default.MEASUREMENT_RANGE[configuration[
                                        "Gene Ontology enrichment"].get(
                                            "score", {}).get(m)])[1],
                                 protein_interaction_network.get_measurements(
                                     network, time, m,
                                     average.SITE_AVERAGE[configuration[
                                         "Gene Ontology enrichment"].get(
                                             "site average", {}).get(
                                                 m,
                                                 "maximum absolute logarithm")],
                                     average.REPLICATE_AVERAGE[configuration[
                                         "Gene Ontology enrichment"].get(
                                             "replicate average",
                                             {}).get(m, "mean")])))

                            if configuration["Gene Ontology enrichment"].get(
                                    "intersection", False):
                                proteins.intersection_update(
                                    protein_interaction_network.get_proteins(
                                        network, time, m,
                                        average.SITE_AVERAGE[configuration[
                                            "Gene Ontology enrichment"].get(
                                                "site average", {}).get(
                                                    m,
                                                    "maximum absolute logarithm"
                                                )],
                                        average.REPLICATE_AVERAGE[configuration[
                                            "Gene Ontology enrichment"].get(
                                                "replicate average",
                                                {}).get(m, "mean")],
                                        measurement_range))

                            else:
                                proteins.update(
                                    protein_interaction_network.get_proteins(
                                        network, time, m,
                                        average.SITE_AVERAGE[configuration[
                                            "Gene Ontology enrichment"].get(
                                                "site average", {}).get(
                                                    m,
                                                    "maximum absolute logarithm"
                                                )],
                                        average.REPLICATE_AVERAGE[configuration[
                                            "Gene Ontology enrichment"].get(
                                                "replicate average",
                                                {}).get(m, "mean")],
                                        measurement_range))

                gene_ontology_enrichment = gene_ontology.get_enrichment(
                    [frozenset(proteins)],
                    reference=[set()]
                    if configuration["Gene Ontology enrichment"].get(
                        "annotation", False) else [network.nodes()],
                    enrichment_test=test.ENRICHMENT_TEST[(
                        configuration["Gene Ontology enrichment"].get(
                            "test", "hypergeometric"),
                        configuration["Gene Ontology enrichment"].get(
                            "increase", True))],
                    multiple_testing_correction=correction.CORRECTION[
                        configuration["Gene Ontology enrichment"].get(
                            "correction", "Benjamini-Yekutieli")],
                    organism=configuration["Gene Ontology enrichment"].get(
                        "organism", 9606),
                    namespaces=[
                        namespace.replace(" ", "_") for namespace in
                        configuration["Gene Ontology enrichment"].get(
                            "namespaces", [
                                "cellular component", "molecular function",
                                "biological process"
                            ])
                    ])

                for (term, name), p in sorted(
                        gene_ontology_enrichment[frozenset(proteins)].items(),
                        key=lambda item: item[1]):
                    if p <= configuration["Gene Ontology enrichment"].get(
                            "p", 1.0):
                        gene_ontology_writer.writerow(
                            ["network", term, name, p])

            elif "Gene Ontology enrichment" in configuration:
                gene_ontology_enrichment = gene_ontology.get_enrichment(
                    [frozenset(network.nodes())],
                    reference=[set()],
                    enrichment_test=test.ENRICHMENT_TEST[(
                        configuration["Gene Ontology enrichment"].get(
                            "test", "hypergeometric"),
                        configuration["Gene Ontology enrichment"].get(
                            "increase", True))],
                    multiple_testing_correction=correction.CORRECTION[
                        configuration["Gene Ontology enrichment"].get(
                            "correction", "Benjamini-Yekutieli")],
                    organism=configuration["Gene Ontology enrichment"].get(
                        "organism", 9606),
                    namespaces=[
                        namespace.replace(" ", "_") for namespace in
                        configuration["Gene Ontology enrichment"].get(
                            "namespaces", [
                                "cellular component", "molecular function",
                                "biological process"
                            ])
                    ])

                for (term,
                     name), p in sorted(gene_ontology_enrichment[frozenset(
                         network.nodes())].items(),
                                        key=lambda item: item[1]):
                    if p <= configuration["Gene Ontology enrichment"].get(
                            "p", 1.0):
                        gene_ontology_writer.writerow(
                            ["network", term, name, p])

            if "PTMs" in configuration.get("community detection",
                                           {}).get("Gene Ontology enrichment",
                                                   {}):
                if configuration["community detection"][
                        "Gene Ontology enrichment"].get("intersection", False):
                    subsets = {
                        community: set(community.nodes())
                        for community in communities
                    }
                else:
                    subsets = {community: set() for community in communities}

                for time in protein_interaction_network.get_times(network):
                    for m in configuration["community detection"][
                            "Gene Ontology enrichment"].get("PTMs", []):
                        if m in protein_interaction_network.get_modifications(
                                network, time):
                            for community in subsets:
                                measurement_range = (
                                    score.MEASUREMENT_SCORE[
                                        configuration["community detection"]
                                        ["Gene Ontology enrichment"].get(
                                            "score", {}).get(m)]
                                    (configuration["community detection"]
                                     ["Gene Ontology enrichment"].get(
                                         "measurement",
                                         default.MEASUREMENT_RANGE[
                                             configuration[
                                                 "community detection"]
                                             ["Gene Ontology enrichment"].get(
                                                 "score", {}).get(m)])[0],
                                     protein_interaction_network.
                                     get_measurements(
                                         network, time, m, average.SITE_AVERAGE[
                                             configuration[
                                                 "community detection"]
                                             ["Gene Ontology enrichment"].get(
                                                 "site average", {}).
                                             get(m,
                                                 "maximum absolute logarithm")],
                                         average.REPLICATE_AVERAGE[
                                             configuration[
                                                 "community detection"]
                                             ["Gene Ontology enrichment"].get(
                                                 "replicate average",
                                                 {}).get(m, "mean")])),
                                    score.MEASUREMENT_SCORE[
                                        configuration["community detection"]
                                        ["Gene Ontology enrichment"].get(
                                            "score", {}).get(m)]
                                    (configuration["community detection"]
                                     ["Gene Ontology enrichment"].get(
                                         "measurement",
                                         default.MEASUREMENT_RANGE[
                                             configuration[
                                                 "community detection"]
                                             ["Gene Ontology enrichment"].get(
                                                 "score", {}).get(m)])[1],
                                     protein_interaction_network.
                                     get_measurements(
                                         network, time, m, average.SITE_AVERAGE[
                                             configuration[
                                                 "community detection"]
                                             ["Gene Ontology enrichment"].get(
                                                 "site average", {}).
                                             get(m,
                                                 "maximum absolute logarithm")],
                                         average.REPLICATE_AVERAGE[
                                             configuration[
                                                 "community detection"]
                                             ["Gene Ontology enrichment"].get(
                                                 "replicate average",
                                                 {}).get(m, "mean")])))

                                if configuration["community detection"][
                                        "Gene Ontology enrichment"].get(
                                            "intersection", False):
                                    subsets[community].intersection_update(
                                        protein_interaction_network.
                                        get_proteins(
                                            community, time, m,
                                            average.SITE_AVERAGE[
                                                configuration[
                                                    "community detection"]
                                                ["Gene Ontology enrichment"].
                                                get("site average", {}).get(
                                                    m,
                                                    "maximum absolute logarithm"
                                                )],
                                            average.REPLICATE_AVERAGE[
                                                configuration[
                                                    "community detection"]
                                                ["Gene Ontology enrichment"].
                                                get("replicate average",
                                                    {}).get(m, "mean")],
                                            measurement_range))

                                else:
                                    subsets[community].update(
                                        protein_interaction_network.
                                        get_proteins(
                                            community, time, m,
                                            average.SITE_AVERAGE[
                                                configuration[
                                                    "community detection"]
                                                ["Gene Ontology enrichment"].
                                                get("site average", {}).get(
                                                    m,
                                                    "maximum absolute logarithm"
                                                )],
                                            average.REPLICATE_AVERAGE[
                                                configuration[
                                                    "community detection"]
                                                ["Gene Ontology enrichment"].
                                                get("replicate average",
                                                    {}).get(m, "mean")],
                                            measurement_range))

                gene_ontology_enrichment = gene_ontology.get_enrichment(
                    [
                        frozenset(subsets[community])
                        for community in communities
                    ],
                    reference=[network.nodes()]
                    if configuration["community detection"]
                    ["Gene Ontology enrichment"].get("network", False) else
                    ([set()] if configuration["community detection"]
                     ["Gene Ontology enrichment"].get("annotation", False) else
                     [community.nodes() for community in communities]),
                    enrichment_test=test.ENRICHMENT_TEST[(
                        configuration["community detection"]
                        ["Gene Ontology enrichment"].get(
                            "test", "hypergeometric"),
                        configuration["community detection"]
                        ["Gene Ontology enrichment"].get("increase", True))],
                    multiple_testing_correction=correction.CORRECTION[
                        configuration["community detection"]
                        ["Gene Ontology enrichment"].get(
                            "correction", "Benjamini-Yekutieli")],
                    organism=configuration["community detection"]
                    ["Gene Ontology enrichment"].get("organism", 9606),
                    namespaces=[
                        namespace.replace(" ", "_")
                        for namespace in configuration["community detection"]
                        ["Gene Ontology enrichment"].get(
                            "namespaces", [
                                "cellular component", "molecular function",
                                "biological process"
                            ])
                    ])

                for k, community in enumerate(sorted(
                        communities,
                        key=lambda community: int(community.number_of_nodes()),
                        reverse=True),
                                              start=1):
                    for (term,
                         name), p in sorted(gene_ontology_enrichment[frozenset(
                             subsets[community])].items(),
                                            key=lambda item: item[1]):
                        if p <= configuration["community detection"][
                                "Gene Ontology enrichment"].get("p", 1.0):
                            export[community] = True
                            gene_ontology_writer.writerow(
                                [f"community {k}", term, name, p])

            elif "Gene Ontology enrichment" in configuration.get(
                    "community detection", {}):
                gene_ontology_enrichment = gene_ontology.get_enrichment(
                    [frozenset(community.nodes()) for community in communities],
                    reference=[set()] if configuration["community detection"]
                    ["Gene Ontology enrichment"].get(
                        "annotation", False) else [network.nodes()],
                    enrichment_test=test.ENRICHMENT_TEST[(
                        configuration["community detection"]
                        ["Gene Ontology enrichment"].get(
                            "test", "hypergeometric"),
                        configuration["community detection"]
                        ["Gene Ontology enrichment"].get("increase", True))],
                    multiple_testing_correction=correction.CORRECTION[
                        configuration["community detection"]
                        ["Gene Ontology enrichment"].get(
                            "correction", "Benjamini-Yekutieli")],
                    organism=configuration["community detection"]
                    ["Gene Ontology enrichment"].get("organism", 9606),
                    namespaces=[
                        namespace.replace(" ", "_")
                        for namespace in configuration["community detection"]
                        ["Gene Ontology enrichment"].get(
                            "namespaces", [
                                "cellular component", "molecular function",
                                "biological process"
                            ])
                    ])

                for k, community in enumerate(sorted(
                        communities,
                        key=lambda community: int(community.number_of_nodes()),
                        reverse=True),
                                              start=1):
                    for (term,
                         name), p in sorted(gene_ontology_enrichment[frozenset(
                             community.nodes())].items(),
                                            key=lambda item: item[1]):
                        if p <= configuration["community detection"][
                                "Gene Ontology enrichment"].get("p", 1.0):
                            export[community] = True
                            gene_ontology_writer.writerow(
                                [f"community {k}", term, name, p])

    if ("Reactome enrichment" in configuration or "Reactome enrichment"
            in configuration.get("community detection", {})):
        with open(f"{identifier}_reactome.tsv",
                  "w",
                  newline="",
                  encoding="utf-8") as reactome_table:
            reactome_writer = csv.writer(reactome_table, dialect="excel-tab")
            reactome_writer.writerow(["network", "pathway", "name", "p-value"])

            if "PTMs" in configuration.get("Reactome enrichment", {}):
                if configuration["Reactome enrichment"].get(
                        "intersection", False):
                    proteins = set(network.nodes())
                else:
                    proteins = set()

                for time in protein_interaction_network.get_times(network):
                    for m in configuration["Reactome enrichment"].get(
                            "PTMs", []):
                        if m in protein_interaction_network.get_modifications(
                                network, time):
                            measurement_range = (
                                score.MEASUREMENT_SCORE[
                                    configuration["Reactome enrichment"].get(
                                        "score", {}).get(m)]
                                (configuration["Reactome enrichment"].get(
                                    "measurement",
                                    default.MEASUREMENT_RANGE[configuration[
                                        "Reactome enrichment"].get(
                                            "score", {}).get(m)])[0],
                                 protein_interaction_network.get_measurements(
                                     network, time, m,
                                     average.SITE_AVERAGE[configuration[
                                         "Reactome enrichment"].get(
                                             "site average", {}).get(
                                                 m,
                                                 "maximum absolute logarithm")],
                                     average.REPLICATE_AVERAGE[configuration[
                                         "Reactome enrichment"].get(
                                             "replicate average",
                                             {}).get(m, "mean")])),
                                score.MEASUREMENT_SCORE[
                                    configuration["Reactome enrichment"].get(
                                        "score", {}).get(m)]
                                (configuration["Reactome enrichment"].get(
                                    "measurement",
                                    default.MEASUREMENT_RANGE[configuration[
                                        "Reactome enrichment"].get(
                                            "score", {}).get(m)])[1],
                                 protein_interaction_network.get_measurements(
                                     network, time, m,
                                     average.SITE_AVERAGE[configuration[
                                         "Reactome enrichment"].get(
                                             "site average", {}).get(
                                                 m,
                                                 "maximum absolute logarithm")],
                                     average.REPLICATE_AVERAGE[configuration[
                                         "Reactome enrichment"].get(
                                             "replicate average",
                                             {}).get(m, "mean")])))

                            if configuration["Reactome enrichment"].get(
                                    "intersection", False):
                                proteins.intersection_update(
                                    protein_interaction_network.get_proteins(
                                        network, time, m, average.SITE_AVERAGE[
                                            configuration["Reactome enrichment"]
                                            .get("site average", {}).get(
                                                m,
                                                "maximum absolute logarithm")],
                                        average.REPLICATE_AVERAGE[configuration[
                                            "Reactome enrichment"].get(
                                                "replicate average",
                                                {}).get(m, "mean")],
                                        measurement_range))

                            else:
                                proteins.update(
                                    protein_interaction_network.get_proteins(
                                        network, time, m, average.SITE_AVERAGE[
                                            configuration["Reactome enrichment"]
                                            .get("site average", {}).get(
                                                m,
                                                "maximum absolute logarithm")],
                                        average.REPLICATE_AVERAGE[configuration[
                                            "Reactome enrichment"].get(
                                                "replicate average",
                                                {}).get(m, "mean")],
                                        measurement_range))

                reactome_enrichment = reactome.get_enrichment(
                    [frozenset(proteins)],
                    reference=[set()]
                    if configuration["Reactome enrichment"].get(
                        "annotation", False) else [network.nodes()],
                    enrichment_test=test.ENRICHMENT_TEST[(
                        configuration["Reactome enrichment"].get(
                            "test", "hypergeometric"),
                        configuration["Reactome enrichment"].get(
                            "increase", True))],
                    multiple_testing_correction=correction.CORRECTION[
                        configuration["Reactome enrichment"].get(
                            "correction", "Benjamini-Yekutieli")],
                    organism=configuration["Reactome enrichment"].get(
                        "organism", 9606))

                for (pathway, name), p in sorted(
                        reactome_enrichment[frozenset(proteins)].items(),
                        key=lambda item: item[1]):
                    if p <= configuration["Reactome enrichment"].get("p", 1.0):
                        reactome_writer.writerow(["network", pathway, name, p])

            elif "Reactome enrichment" in configuration:
                reactome_enrichment = reactome.get_enrichment(
                    [frozenset(network.nodes())],
                    reference=[set()],
                    enrichment_test=test.ENRICHMENT_TEST[(
                        configuration["Reactome enrichment"].get(
                            "test", "hypergeometric"),
                        configuration["Reactome enrichment"].get(
                            "increase", True))],
                    multiple_testing_correction=correction.CORRECTION[
                        configuration["Reactome enrichment"].get(
                            "correction", "Benjamini-Yekutieli")],
                    organism=configuration["Reactome enrichment"].get(
                        "organism", 9606))

                for (pathway, name), p in sorted(reactome_enrichment[frozenset(
                        network.nodes())].items(),
                                                 key=lambda item: item[1]):
                    if p <= configuration["Reactome enrichment"].get("p", 1.0):
                        reactome_writer.writerow(["network", pathway, name, p])

            if "PTMs" in configuration.get("community detection",
                                           {}).get("Reactome enrichment", {}):
                if configuration["community detection"][
                        "Reactome enrichment"].get("intersection", False):
                    subsets = {
                        community: set(community.nodes())
                        for community in communities
                    }
                else:
                    subsets = {community: set() for community in communities}

                for time in protein_interaction_network.get_times(network):
                    for m in configuration["community detection"][
                            "Reactome enrichment"].get("PTMs", []):
                        if m in protein_interaction_network.get_modifications(
                                network, time):
                            for community in subsets:
                                measurement_range = (
                                    score.MEASUREMENT_SCORE[
                                        configuration["community detection"]
                                        ["Reactome enrichment"].get(
                                            "score", {}).get(m)]
                                    (configuration["community detection"]
                                     ["Reactome enrichment"].get(
                                         "measurement",
                                         default.MEASUREMENT_RANGE[
                                             configuration[
                                                 "community detection"]
                                             ["Reactome enrichment"].get(
                                                 "score", {}).get(m)])[0],
                                     protein_interaction_network.
                                     get_measurements(
                                         network, time, m, average.SITE_AVERAGE[
                                             configuration[
                                                 "community detection"]
                                             ["Reactome enrichment"].get(
                                                 "site average", {}).
                                             get(m,
                                                 "maximum absolute logarithm")],
                                         average.REPLICATE_AVERAGE[
                                             configuration[
                                                 "community detection"]
                                             ["Reactome enrichment"].get(
                                                 "replicate average",
                                                 {}).get(m, "mean")])),
                                    score.MEASUREMENT_SCORE[
                                        configuration["community detection"]
                                        ["Reactome enrichment"].get(
                                            "score", {}).get(m)]
                                    (configuration["community detection"]
                                     ["Reactome enrichment"].get(
                                         "measurement",
                                         default.MEASUREMENT_RANGE[
                                             configuration[
                                                 "community detection"]
                                             ["Reactome enrichment"].get(
                                                 "score", {}).get(m)])[1],
                                     protein_interaction_network.
                                     get_measurements(
                                         network, time, m, average.SITE_AVERAGE[
                                             configuration[
                                                 "community detection"]
                                             ["Reactome enrichment"].get(
                                                 "site average", {}).
                                             get(m,
                                                 "maximum absolute logarithm")],
                                         average.REPLICATE_AVERAGE[
                                             configuration[
                                                 "community detection"]
                                             ["Reactome enrichment"].get(
                                                 "replicate average",
                                                 {}).get(m, "mean")])))

                                if configuration["community detection"][
                                        "Reactome enrichment"].get(
                                            "intersection", False):
                                    subsets[community].intersection_update(
                                        protein_interaction_network.
                                        get_proteins(
                                            community, time, m,
                                            average.SITE_AVERAGE[
                                                configuration[
                                                    "community detection"]
                                                ["Reactome enrichment"].
                                                get("site average", {}).get(
                                                    m,
                                                    "maximum absolute logarithm"
                                                )], average.REPLICATE_AVERAGE[
                                                    configuration[
                                                        "community detection"]
                                                    ["Reactome enrichment"].get(
                                                        "replicate average",
                                                        {}).get(m, "mean")],
                                            measurement_range))

                                else:
                                    subsets[community].update(
                                        protein_interaction_network.
                                        get_proteins(
                                            community, time, m,
                                            average.SITE_AVERAGE[
                                                configuration[
                                                    "community detection"]
                                                ["Reactome enrichment"].
                                                get("site average", {}).get(
                                                    m,
                                                    "maximum absolute logarithm"
                                                )], average.REPLICATE_AVERAGE[
                                                    configuration[
                                                        "community detection"]
                                                    ["Reactome enrichment"].get(
                                                        "replicate average",
                                                        {}).get(m, "mean")],
                                            measurement_range))

                reactome_enrichment = reactome.get_enrichment(
                    [
                        frozenset(subsets[community])
                        for community in communities
                    ],
                    reference=[network.nodes()]
                    if configuration["community detection"]
                    ["Reactome enrichment"].get("network", False) else
                    ([set()] if configuration["community detection"]
                     ["Reactome enrichment"].get("annotation", False) else
                     [community.nodes() for community in communities]),
                    enrichment_test=test.ENRICHMENT_TEST[(
                        configuration["community detection"]
                        ["Reactome enrichment"].get("test", "hypergeometric"),
                        configuration["community detection"]
                        ["Reactome enrichment"].get("increase", True))],
                    multiple_testing_correction=correction.CORRECTION[
                        configuration["community detection"]
                        ["Reactome enrichment"].get("correction",
                                                    "Benjamini-Yekutieli")],
                    organism=configuration["community detection"]
                    ["Reactome enrichment"].get("organism", 9606))

                for k, community in enumerate(sorted(
                        communities,
                        key=lambda community: int(community.number_of_nodes()),
                        reverse=True),
                                              start=1):
                    for (pathway,
                         name), p in sorted(reactome_enrichment[frozenset(
                             subsets[community])].items(),
                                            key=lambda item: item[1]):
                        if p <= configuration["community detection"][
                                "Reactome enrichment"].get("p", 1.0):
                            export[community] = True
                            reactome_writer.writerow(
                                [f"community {k}", pathway, name, p])

            elif "Reactome enrichment" in configuration:
                reactome_enrichment = reactome.get_enrichment(
                    [frozenset(community.nodes()) for community in communities],
                    reference=[set()] if configuration["community detection"]
                    ["Reactome enrichment"].get("annotation",
                                                False) else [network.nodes()],
                    enrichment_test=test.ENRICHMENT_TEST[(
                        configuration["community detection"]
                        ["Reactome enrichment"].get("test", "hypergeometric"),
                        configuration["community detection"]
                        ["Reactome enrichment"].get("increase", True))],
                    multiple_testing_correction=correction.CORRECTION[
                        configuration["community detection"]
                        ["Reactome enrichment"].get("correction",
                                                    "Benjamini-Yekutieli")],
                    organism=configuration["community detection"]
                    ["Reactome enrichment"].get("organism", 9606))

                for k, community in enumerate(sorted(
                        communities,
                        key=lambda community: int(community.number_of_nodes()),
                        reverse=True),
                                              start=1):
                    for (pathway,
                         name), p in sorted(reactome_enrichment[frozenset(
                             community.nodes())].items(),
                                            key=lambda item: item[1]):
                        if p <= configuration["community detection"][
                                "Reactome enrichment"].get("p", 1.0):
                            export[community] = True
                            reactome_writer.writerow(
                                [f"community {k}", pathway, name, p])

    if ("measurement enrichment" in configuration.get("community detection",
                                                      {})):
        with open(f"{identifier}_measurement_enrichment.tsv",
                  "w",
                  newline="",
                  encoding="utf-8") as measurement_enrichment_table:
            measurement_enrichment_writer = csv.writer(
                measurement_enrichment_table, dialect="excel-tab")
            measurement_enrichment_writer.writerow(
                ["community", "time", "PTM", "p-value"])

            measurements = {
                modification:
                default.MEASUREMENT_RANGE.get(score,
                                              default.MEASUREMENT_RANGE[None])
                for modification, score in configuration["community detection"]
                ["measurement enrichment"].get("score", {}).items()
            }

            for modification, measurement_range in configuration[
                    "community detection"]["measurement enrichment"].get(
                        "measurement", {}).items():
                measurements[modification] = measurement_range

            enrichment = protein_interaction_network.get_enrichment(
                network,
                communities,
                measurements=measurements,
                measurement_score={
                    modification:
                    score.MEASUREMENT_SCORE.get(measurement_score,
                                                score.MEASUREMENT_SCORE[None])
                    for modification, measurement_score in
                    configuration["community detection"]
                    ["measurement enrichment"].get("score", {})
                },
                site_average={
                    modification: average.SITE_AVERAGE.get(
                        site_average,
                        average.SITE_AVERAGE["maximum absolute logarithm"])
                    if site_average is not None else None for modification,
                    site_average in configuration["community detection"]
                    ["measurement enrichment"].get("site average", {}).items()
                },
                replicate_average={
                    modification: average.REPLICATE_AVERAGE.get(
                        replicate_average, average.REPLICATE_AVERAGE["mean"])
                    if replicate_average is not None else None for modification,
                    replicate_average in configuration["community detection"]
                    ["measurement enrichment"].get("replicate average",
                                                   {}).items()
                },
                enrichment_test=test.ENRICHMENT_TEST[(
                    configuration["community detection"]
                    ["measurement enrichment"].get("test", "hypergeometric"),
                    configuration["community detection"]
                    ["measurement enrichment"].get("increase", True))],
                multiple_testing_correction=correction.CORRECTION[
                    configuration["community detection"]
                    ["measurement enrichment"].get("correction",
                                                   "Benjamini-Yekutieli")])

            for k, community in enumerate(sorted(
                    communities,
                    key=lambda community: int(community.number_of_nodes()),
                    reverse=True),
                                          start=1):
                for time in enrichment[community]:
                    for modification, p in sorted(
                            enrichment[community][time].items(),
                            key=lambda item: item[1]):
                        if p <= configuration["community detection"][
                                "measurement enrichment"].get("p", 1.0):
                            export[community] = True
                            measurement_enrichment_writer.writerow(
                                [f"community {k}", time, modification, p])

    if "measurement location" in configuration.get("community detection", {}):
        with open(f"{identifier}_measurement_location.tsv",
                  "w",
                  newline="",
                  encoding="utf-8") as measurement_location_table:
            measurement_location_writer = csv.writer(measurement_location_table,
                                                     dialect="excel-tab")
            measurement_location_writer.writerow(
                ["community", "time", "PTM", "p-value"])

            location = protein_interaction_network.get_location(
                network,
                communities,
                site_average={
                    modification: average.SITE_AVERAGE.get(
                        site_average,
                        average.SITE_AVERAGE["maximum absolute logarithm"])
                    if site_average is not None else None for modification,
                    site_average in configuration["community detection"]
                    ["measurement location"].get("site average", {}).items()
                },
                replicate_average={
                    modification: average.REPLICATE_AVERAGE.get(
                        replicate_average, average.REPLICATE_AVERAGE["mean"])
                    if replicate_average is not None else None
                    for modification, replicate_average in
                    configuration["community detection"]["measurement location"]
                    .get("replicate average", {}).items()
                },
                location_test=test.LOCATION_TEST[(
                    configuration["community detection"]
                    ["measurement location"].get("test",
                                                 "Mann-Whitney-Wilcoxon"),
                    configuration["community detection"]
                    ["measurement location"].get("increase", True),
                    configuration["community detection"]
                    ["measurement location"].get("absolute", True))],
                multiple_testing_correction=correction.CORRECTION[
                    configuration["community detection"]
                    ["measurement location"].get("correction",
                                                 "Benjamini-Yekutieli")])

            for k, community in enumerate(sorted(
                    communities,
                    key=lambda community: int(community.number_of_nodes()),
                    reverse=True),
                                          start=1):
                for time in location[community]:
                    for modification, p in sorted(
                            location[community][time].items(),
                            key=lambda item: item[1]):
                        if p <= configuration["community detection"][
                                "measurement location"].get("p", 1.0):
                            export[community] = True
                            measurement_location_writer.writerow(
                                [f"community {k}", time, modification, p])

    for k, community in enumerate(sorted(
            communities,
            key=lambda community: int(community.number_of_nodes()),
            reverse=True),
                                  start=1):
        if export[community]:
            protein_interaction_network.export(community, f"{identifier}_{k}")


def process_configuration(
        configurations: Mapping[str, Mapping[str, Any]]) -> None:
    """
    Executes workflows specified in configurations sequentially.

    Args:
        configurations: The specification of workflows.
    """
    for identifier, configuration in configurations.items():
        process_workflow(identifier, configuration)


def process_configuration_file(configuration_file: str) -> None:
    """
    Launches execution of a workflow.

    Args:
        configuration_file: file name of configuration file.
    """
    with open(configuration_file, encoding="utf-8") as configuration:
        process_configuration(json.load(configuration))


def main() -> None:
    """Concurrent workflow execution."""
    parser = argparse.ArgumentParser(
        description="DIANA: data integration and network analysis for "
        "post-translational modification mass spectrometry data")

    parser.add_argument("-c",
                        "--configuration",
                        help="configuration files",
                        nargs="+",
                        required=True)

    parser.add_argument(
        "-p",
        "--processes",
        help="maximum number of concurrently processed configuration files "
        f"(default: {os.cpu_count()})",
        type=int,
        default=os.cpu_count())

    args = parser.parse_args()

    with concurrent.futures.ProcessPoolExecutor(
            max_workers=args.processes) as executor:
        for process in executor.map(process_configuration_file,
                                    args.configuration):
            if process:
                process.results()


if __name__ == "__main__":
    main()
