"""Cytoscape style specifications"""
import json
import xml.etree.ElementTree as ET
from typing import Callable, Collection

import networkx as nx
from networks import (ontology_network, pathway_network,
                      protein_protein_interaction_network)

from cytoscape.styles import ontology_network as ontology_network_style
from cytoscape.styles import pathway_network as pathway_network_style
from cytoscape.styles import \
    protein_protein_interaction_network as \
    protein_protein_interaction_network_style


def get_bar_chart(
    time: int,
    modification: str,
    sites: int,
    cy_range: tuple[float, float] = (-2.0, 2.0)) -> str:
    """
    Returns a bar chart specification for Cytoscape styles.

    Args:
        time: time of measurement associated with the change
        modification: modification associated with the change
        cy_range: range of log2-fold changes covered by the bar chart.

    Returns:
       bar chart specification
    """
    bar_chart = json.dumps({
        "cy_range":
            cy_range,
        "cy_showRangeAxis":
            True,
        "cy_type":
            "UP_DOWN",
        "cy_autoRange":
            False,
        "cy_colorScheme":
            "BLUE_RED",
        "cy_showRangeZeroBaseline":
            True,
        "cy_colors": ["#FF0000", "#0000FF"],
        "cy_dataColumns": [
            f"{time} {modification} {site}" for site in range(1, sites + 1)
        ],
    })
    return f"org.cytoscape.BarChart: {bar_chart}"


def get_protein_protein_interaction_network_styles(
    network: nx.Graph,
    bar_chart_range: tuple[float, float] = (-1.0, 1.0),
    convert_change: Callable[[float, Collection[float]],
                             float] = lambda change, changes: change,
    site_combination: Callable[[Collection[float]],
                               float] = lambda sites: max(sites, key=abs),
    confidence_score_combination: Callable[[dict[str, float]], float] = lambda
    confidence_scores: float(bool(confidence_scores.values()))
) -> ET.ElementTree:
    """
    Returns the Cytoscape styles for a protein-protein interaction network.

    Args:
        network: The protein-protein interaction network.
        bar_chart_range: The range of log2-fold changes covered by the bar
            chart.
        get_change: The function to transform a proteins' log2-fold change.
        site_combination: The function to derive a proteins' representative
            log2-fold change from its site-specific changes.
        confidence_score_combination: The function to derive an edges'
            representative confidence from its confidence scores.

    Returns:
       The Cytoscape styles for the protein-protein interaction network.
    """
    styles = ET.ElementTree(
        ET.Element("vizmap", attrib={
            "id": "VizMap",
            "documentVersion": "3.0"
        }))

    for time in protein_protein_interaction_network.get_times(network):
        modifications = protein_protein_interaction_network.get_post_translational_modifications(
            network, time)
        visual_style_sub_element = ET.SubElement(styles.getroot(),
                                                 "visualStyle",
                                                 attrib={"name": str(time)})

        for component in protein_protein_interaction_network_style.COMPONENTS[
                len(modifications) - 1]:
            component_sub_element = ET.SubElement(visual_style_sub_element,
                                                  component)

            for name, dependency in protein_protein_interaction_network_style.COMPONENTS[
                    len(modifications) - 1][component]["dependency"].items():
                ET.SubElement(
                    component_sub_element,
                    "dependency",
                    attrib={
                        "name": name,
                        "value": dependency["value"]
                    },
                )

            for name, visual_property in protein_protein_interaction_network_style.COMPONENTS[
                    len(modifications) -
                    1][component]["visualProperty"].items():
                visual_property_sub_element = ET.SubElement(
                    component_sub_element,
                    "visualProperty",
                    attrib={
                        "name": name,
                        "default": visual_property["default"]
                    },
                )

                if visual_property.get("continuousMapping"):
                    continuous_mapping_sub_element = ET.SubElement(
                        visual_property_sub_element,
                        "continuousMapping",
                        attrib={
                            "attributeName":
                                visual_property["continuousMapping"]
                                ["attributeName"],
                            "attributeType":
                                visual_property["continuousMapping"]
                                ["attributeType"]
                        })

                    for key, values in visual_property["continuousMapping"][
                            "continuousMappingPoint"].items():
                        ET.SubElement(
                            continuous_mapping_sub_element,
                            "continuousMappingPoint",
                            attrib={
                                "attrValue":
                                    key.format(
                                        max=confidence_score_combination({
                                            database: 1.0 for database in
                                            protein_protein_interaction_network.
                                            get_databases(network)
                                        })),
                                "equalValue":
                                    values["equalValue"],
                                "greaterValue":
                                    values["greaterValue"],
                                "lesserValue":
                                    values["lesserValue"]
                            },
                        )

                elif visual_property.get("discreteMapping"):
                    discrete_mapping_sub_element = ET.SubElement(
                        visual_property_sub_element,
                        "discreteMapping",
                        attrib={
                            "attributeName":
                                visual_property["discreteMapping"]
                                ["attributeName"].format(time=time),
                            "attributeType":
                                visual_property["discreteMapping"]
                                ["attributeType"],
                        },
                    )

                    for key, value in visual_property["discreteMapping"][
                            "discreteMappingEntry"].items():
                        ET.SubElement(
                            discrete_mapping_sub_element,
                            "discreteMappingEntry",
                            attrib={
                                "attributeValue":
                                    key.format(modifications=modifications),
                                "value":
                                    value,
                            },
                        )

                elif visual_property.get("passthroughMapping"):
                    ET.SubElement(
                        visual_property_sub_element,
                        "passthroughMapping",
                        attrib={
                            "attributeName":
                                visual_property["passthroughMapping"]
                                ["attributeName"],
                            "attributeType":
                                visual_property["passthroughMapping"]
                                ["attributeType"],
                        },
                    )

        visual_property_sub_elements = visual_style_sub_element.find(
            "node").findall("visualProperty")

        for i, modification in enumerate(modifications):
            if i < 2:
                for visual_property_sub_element in visual_property_sub_elements:
                    if visual_property_sub_element.get(
                            "name") == f"NODE_CUSTOMGRAPHICS_{i+1}":
                        visual_property_sub_element.set(
                            "default",
                            get_bar_chart(
                                time,
                                modification,
                                protein_protein_interaction_network.get_sites(
                                    network, time, modification),
                                cy_range=(
                                    convert_change(
                                        bar_chart_range[0],
                                        protein_protein_interaction_network.
                                        get_changes(network, time, modification,
                                                    site_combination)),
                                    convert_change(
                                        bar_chart_range[1],
                                        protein_protein_interaction_network.
                                        get_changes(network, time, modification,
                                                    site_combination)))))

                    elif visual_property_sub_element.get(
                            "name") == f"NODE_CUSTOMGRAPHICS_POSITION_{i + 1}":
                        visual_property_sub_element.set(
                            "default",
                            f"{('W', 'E')[i]},{('E', 'W')[i]},c,0.00,0.00",
                        )

    ET.indent(styles)

    return styles


def get_gene_ontology_network_style(network: nx.Graph) -> ET.ElementTree:
    """
    Returns the Cytoscape styles for a Gene Ontology network.

    Args:
        network: The Gene Ontology network.

    Returns:
        The Cytoscape style for the Gene Ontology network.
    """
    style = ET.ElementTree(
        ET.Element("vizmap", attrib={
            "id": "VizMap",
            "documentVersion": "3.0"
        }))

    visual_style_sub_element = ET.SubElement(style.getroot(),
                                             "visualStyle",
                                             attrib={"name": "ontology"})

    for component in ontology_network_style.COMPONENTS:
        component_sub_element = ET.SubElement(visual_style_sub_element,
                                              component)

        for name, dependency in ontology_network_style.COMPONENTS[component][
                "dependency"].items():
            ET.SubElement(
                component_sub_element,
                "dependency",
                attrib={
                    "name": name,
                    "value": dependency["value"]
                },
            )

        for name, visual_property in ontology_network_style.COMPONENTS[
                component]["visualProperty"].items():
            visual_property_sub_element = ET.SubElement(
                component_sub_element,
                "visualProperty",
                attrib={
                    "name": name,
                    "default": visual_property["default"]
                },
            )

            if visual_property.get("continuousMapping"):
                continuous_mapping_sub_element = ET.SubElement(
                    visual_property_sub_element,
                    "continuousMapping",
                    attrib={
                        "attributeName":
                            visual_property["continuousMapping"]
                            ["attributeName"],
                        "attributeType":
                            visual_property["continuousMapping"]
                            ["attributeType"]
                    })

                for key, values in visual_property["continuousMapping"][
                        "continuousMappingPoint"].items():
                    ET.SubElement(
                        continuous_mapping_sub_element,
                        "continuousMappingPoint",
                        attrib={
                            "attrValue":
                                key.format(max=float(
                                    max(
                                        ontology_network.get_term_sizes(
                                            network).values()))),
                            "equalValue":
                                values["equalValue"].format(size=35.0 + float(
                                    max(
                                        ontology_network.get_term_sizes(
                                            network).values()))),
                            "greaterValue":
                                values["greaterValue"].format(size=35.0 + float(
                                    max(
                                        ontology_network.get_term_sizes(
                                            network).values()))),
                            "lesserValue":
                                values["lesserValue"].format(size=35.0 + float(
                                    max(
                                        ontology_network.get_term_sizes(
                                            network).values())))
                        },
                    )

            elif visual_property.get("discreteMapping"):
                discrete_mapping_sub_element = ET.SubElement(
                    visual_property_sub_element,
                    "discreteMapping",
                    attrib={
                        "attributeName":
                            visual_property["discreteMapping"]["attributeName"],
                        "attributeType":
                            visual_property["discreteMapping"]["attributeType"],
                    },
                )

                for key, value in visual_property["discreteMapping"][
                        "discreteMappingEntry"].items():
                    ET.SubElement(
                        discrete_mapping_sub_element,
                        "discreteMappingEntry",
                        attrib={
                            "attributeValue": key,
                            "value": value,
                        },
                    )

            elif visual_property.get("passthroughMapping"):
                ET.SubElement(
                    visual_property_sub_element,
                    "passthroughMapping",
                    attrib={
                        "attributeName":
                            visual_property["passthroughMapping"]
                            ["attributeName"],
                        "attributeType":
                            visual_property["passthroughMapping"]
                            ["attributeType"],
                    },
                )

    ET.indent(style)

    return style


def get_reactome_network_style(network: nx.Graph) -> ET.ElementTree:
    """
    Returns the Cytoscape styles for a Reactome network.

    Args:
        network: The Reactome network.

    Returns:
        The Cytoscape style for the Reactome network.
    """
    style = ET.ElementTree(
        ET.Element("vizmap", attrib={
            "id": "VizMap",
            "documentVersion": "3.0"
        }))

    visual_style_sub_element = ET.SubElement(style.getroot(),
                                             "visualStyle",
                                             attrib={"name": "pathway"})

    for component in pathway_network_style.COMPONENTS:
        component_sub_element = ET.SubElement(visual_style_sub_element,
                                              component)

        for name, dependency in pathway_network_style.COMPONENTS[component][
                "dependency"].items():
            ET.SubElement(
                component_sub_element,
                "dependency",
                attrib={
                    "name": name,
                    "value": dependency["value"]
                },
            )

        for name, visual_property in pathway_network_style.COMPONENTS[
                component]["visualProperty"].items():
            visual_property_sub_element = ET.SubElement(
                component_sub_element,
                "visualProperty",
                attrib={
                    "name": name,
                    "default": visual_property["default"]
                },
            )

            if visual_property.get("continuousMapping"):
                continuous_mapping_sub_element = ET.SubElement(
                    visual_property_sub_element,
                    "continuousMapping",
                    attrib={
                        "attributeName":
                            visual_property["continuousMapping"]
                            ["attributeName"],
                        "attributeType":
                            visual_property["continuousMapping"]
                            ["attributeType"]
                    })

                for key, values in visual_property["continuousMapping"][
                        "continuousMappingPoint"].items():
                    ET.SubElement(
                        continuous_mapping_sub_element,
                        "continuousMappingPoint",
                        attrib={
                            "attrValue":
                                key.format(max=float(
                                    max(
                                        pathway_network.get_pathway_sizes(
                                            network).values()))),
                            "equalValue":
                                values["equalValue"].format(size=35.0 + float(
                                    max(
                                        pathway_network.get_pathway_sizes(
                                            network).values()))),
                            "greaterValue":
                                values["greaterValue"].format(size=35.0 + float(
                                    max(
                                        pathway_network.get_pathway_sizes(
                                            network).values()))),
                            "lesserValue":
                                values["lesserValue"].format(size=35.0 + float(
                                    max(
                                        pathway_network.get_pathway_sizes(
                                            network).values())))
                        },
                    )

            elif visual_property.get("discreteMapping"):
                discrete_mapping_sub_element = ET.SubElement(
                    visual_property_sub_element,
                    "discreteMapping",
                    attrib={
                        "attributeName":
                            visual_property["discreteMapping"]["attributeName"],
                        "attributeType":
                            visual_property["discreteMapping"]["attributeType"],
                    },
                )

                for key, value in visual_property["discreteMapping"][
                        "discreteMappingEntry"].items():
                    ET.SubElement(
                        discrete_mapping_sub_element,
                        "discreteMappingEntry",
                        attrib={
                            "attributeValue": key,
                            "value": value,
                        },
                    )

            elif visual_property.get("passthroughMapping"):
                ET.SubElement(
                    visual_property_sub_element,
                    "passthroughMapping",
                    attrib={
                        "attributeName":
                            visual_property["passthroughMapping"]
                            ["attributeName"],
                        "attributeType":
                            visual_property["passthroughMapping"]
                            ["attributeType"],
                    },
                )

    ET.indent(style)

    return style


def export(styles: ET.ElementTree, basename: str) -> None:
    """
    Exports the Cytoscape styles.

    Args:
        styles: The Cytoscape styles.
        basename: The base file name.
    """
    styles.write(
        f"{basename}.xml",
        encoding="utf-8",
        xml_declaration=True,
    )
