from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from policy_tracker.item_extraction import extract_agenda_items_from_text_path


class ItemExtractionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_extracts_community_services_items(self) -> None:
        path = self.repo_root / "tests" / "fixtures" / "community_services_sample.txt"
        document = extract_agenda_items_from_text_path(path)

        self.assertEqual(document.cluster_name, "Community Services Cluster")
        self.assertEqual(document.meeting_date, "May 20, 2026")
        self.assertEqual(document.meeting_date_iso, "2026-05-20")
        self.assertEqual(document.document_role, "agenda")
        self.assertEqual(document.item_count, 3)
        self.assertEqual(document.items[0].meeting_date_iso, "2026-05-20")
        self.assertEqual(document.items[0].document_role, "agenda")
        self.assertIn("contracting", document.items[0].topic_tags)
        self.assertIn("governance", document.items[2].topic_tags)

    def test_extracts_public_safety_items_and_topics(self) -> None:
        path = self.repo_root / "tests" / "fixtures" / "public_safety_sample.txt"
        document = extract_agenda_items_from_text_path(path)

        self.assertEqual(document.cluster_name, "Public Safety Cluster")
        self.assertEqual(document.item_count, 3)
        probation_item = document.items[2]
        self.assertIn("public_safety", probation_item.topic_tags)
        self.assertIn("probation", probation_item.topic_tags)
        self.assertIn("contracting", probation_item.topic_tags)
        self.assertTrue(probation_item.speakers)

    def test_extracts_homelessness_housing_items_from_roman_numeral_agenda(self) -> None:
        path = self.repo_root / "tests" / "fixtures" / "homelessness_housing_sample.txt"
        document = extract_agenda_items_from_text_path(path)

        self.assertEqual(document.cluster_name, "Homelessness & Housing Cluster")
        self.assertEqual(document.meeting_date, "May 14, 2026")
        self.assertEqual(document.meeting_date_iso, "2026-05-14")
        self.assertEqual(document.item_count, 4)
        self.assertEqual(document.items[0].item_type, "cluster_agenda_item")
        self.assertIn("homelessness", document.items[0].topic_tags)
        self.assertIn("housing", document.items[1].topic_tags)
        self.assertIn("Manny Ruiz", document.items[2].speakers[0])

    def test_extracts_homelessness_housing_policy_deputies_format(self) -> None:
        sample_text = """
        HOMELESS POLICY DEPUTIES MEETING AGENDA
        MEETING WILL TAKE PLACE 100% VIRTUALLY
        Date: Thursday, June 12, 2025
        Time: 2:00 - 4:00 PM
        AGENDA ITEM LEAD
        I. Welcome and Introductions Lilit Bagdzhyan, Fifth District
        II. New Department Update
        Epifanio Peinado
        Temporary Services Administrator,
        CEO Implementation Team
        III.
        Update on New Department
        Listening Sessions
        Leepi Shimkhada
        Deputy Director, Housing for Health,
        LA County Department of Health Services
        VII. Public Comment*
        NEXT MEETING: June 26, 2025
        """
        document = extract_agenda_items_from_text_path(
            self._write_temp_fixture("homeless_policy_deputies_sample.txt", sample_text)
        )

        self.assertEqual(document.cluster_name, "Homelessness & Housing Cluster")
        self.assertEqual(document.meeting_date, "Thursday, June 12, 2025")
        self.assertEqual(document.meeting_date_iso, "2025-06-12")
        self.assertEqual(document.item_count, 2)
        self.assertEqual(document.items[0].title, "New Department Update")
        self.assertIn("Listening Sessions", document.items[1].text_block)

    def test_extracts_homelessness_housing_agenda_review_format_without_header_bloat(self) -> None:
        sample_text = """
        DATE: April 23, 2026
        TIME: 2:00PM - 4:00PM
        Board of Supervisors
        Homelessness & Housing Cluster
        Agenda Review Meeting

        II. Board Motion(s): 2:05-2:35
        a. Approving Homekey+ Program Applications and Resolutions
        Presenter: Anthony Cespedes, First District

        III. Board Letter(s):
        a. None.

        IV. Presentation/Discussion Item(s): 2:35-3:40pm
        a. Housing Ordinances Update (2:50-3:10)
        Presenters:
        • Amy Bodek, Director, Los Angeles County Department of Regional Planning
        • Connie Chung, Deputy Director, Advance Planning Division, Los Angeles County Department of Regional Planning

        Members of the public may address the Homelessness & Housing Cluster on any agenda item during general public comment.
        AGN. NO.__________
        MOTION BY SUPERVISOR HILDA L. SOLIS
        """
        document = extract_agenda_items_from_text_path(
            self._write_temp_fixture("homeless_agenda_review_sample.txt", sample_text)
        )

        self.assertEqual(document.cluster_name, "Homelessness & Housing Cluster")
        self.assertEqual(document.meeting_date, "April 23, 2026")
        self.assertEqual(document.meeting_date_iso, "2026-04-23")
        self.assertEqual(document.item_count, 2)
        self.assertEqual(document.items[0].title, "Approving Homekey+ Program Applications and Resolutions")
        self.assertEqual(document.items[1].title, "Housing Ordinances Update")
        self.assertIn("Amy Bodek", document.items[1].text_block)
        self.assertNotIn("AGN. NO.", document.items[1].text_block)

    def test_extracts_county_motion_line_variant_items(self) -> None:
        path = self.repo_root / "tests" / "fixtures" / "community_services_motion_variant_sample.txt"
        document = extract_agenda_items_from_text_path(path)

        self.assertEqual(document.cluster_name, "Community Services Cluster")
        self.assertEqual(document.meeting_date, "December 10, 2025")
        self.assertEqual(document.item_count, 1)
        self.assertEqual(document.items[0].item_label, "SD-5")
        self.assertEqual(document.items[0].item_type, "board_motion")
        self.assertIn("Rebuild LA County Parks", document.items[0].title)

    def test_extracts_primegov_city_committee_items(self) -> None:
        path = self.repo_root / "tests" / "fixtures" / "la_city_primegov_sample.html.txt"
        document = extract_agenda_items_from_text_path(path, parser_name="la_city_primegov_html")

        self.assertEqual(document.cluster_name, "Housing and Homelessness Committee")
        self.assertEqual(document.meeting_date, "Wednesday, May 21, 2025")
        self.assertEqual(document.meeting_date_iso, "2025-05-21")
        self.assertEqual(document.item_count, 2)
        self.assertEqual(document.items[0].item_label, "1")
        self.assertEqual(document.items[0].section_title, "ITEM(S)")
        self.assertIn("Council File: 23-1182", document.items[0].text_block)
        self.assertIn("homelessness", document.items[0].topic_tags)
        self.assertIn("data_systems", document.items[1].topic_tags)

    def test_extracts_bos_statement_of_proceedings_items(self) -> None:
        path = self.repo_root / "tests" / "fixtures" / "bos_sop_sample.txt"
        document = extract_agenda_items_from_text_path(path, parser_name="la_county_bos_sop_text")

        self.assertEqual(document.cluster_name, "Los Angeles County Board of Supervisors")
        self.assertEqual(document.meeting_date, "Tuesday, April 14, 2026")
        self.assertEqual(document.meeting_date_iso, "2026-04-14")
        self.assertEqual(document.document_role, "proceedings")
        self.assertEqual(document.item_count, 3)
        self.assertEqual(document.items[0].section_title, "CONSENT CALENDAR")
        self.assertEqual(document.items[0].item_type, "bos_sop_item")
        self.assertEqual(document.items[1].item_type, "board_motion")
        self.assertEqual(document.items[2].item_type, "public_hearing")
        self.assertEqual(document.items[1].document_role, "proceedings")
        self.assertEqual(document.items[1].motion_by, "Solis")
        self.assertEqual(document.items[1].second_by, "Hahn")
        self.assertEqual(document.items[1].final_action, "approved")
        self.assertIn("Attachments: Motion by Supervisor Solis", document.items[1].text_block)

    def test_extracts_bos_set_matter_item(self) -> None:
        sample_text = """
        STATEMENT OF PROCEEDINGS FOR THE
        REGULAR MEETING OF THE BOARD OF SUPERVISORS
        Tuesday, August 12, 2025

        I.
        SET MATTER
        Set Matter - 1. 11:00 A.M.
        Report on the County's Budget
        Report by the Chief Executive Officer on the County's budget, including the latest Federal and State policy changes. (25-4327)
        Mark Ramos addressed the Board.
        Attachments:
        Presentation
        Audio

        II. CONSENT CALENDAR
        """
        document = extract_agenda_items_from_text_path(
            self._write_temp_fixture("bos_set_matter_sample.txt", sample_text),
            parser_name="la_county_bos_sop_text",
        )

        self.assertEqual(document.item_count, 1)
        self.assertEqual(document.items[0].item_label, "1")
        self.assertEqual(document.items[0].section_title, "SET MATTER")
        self.assertIn("Report on the County's Budget", document.items[0].title)

    def test_extracts_bos_public_hearing_item_with_wrapped_title(self) -> None:
        sample_text = """
        STATEMENT OF PROCEEDINGS FOR THE
        PUBLIC HEARING MEETING OF THE BOARD OF SUPERVISORS
        Tuesday, March 24, 2026

        II. PUBLIC HEARINGS     1 - 8
        1. Hearing on Resolution to Vacate Alleys East of the Intersection of Miramonte
        Boulevard and 58th Drive in the Unincorporated Community of
        Florence-Firestone
        Hearing on the proposed vacation of the alleys east of the intersection of Miramonte Boulevard and 58th Drive. (26-1446)
        The Department of Public Works submitted a written statement for the record.
        Page 3County of Los Angeles

        III. ADMINISTRATIVE MATTERS
        """
        document = extract_agenda_items_from_text_path(
            self._write_temp_fixture("bos_public_hearing_sample.txt", sample_text),
            parser_name="la_county_bos_sop_text",
        )

        self.assertEqual(document.item_count, 1)
        self.assertEqual(document.items[0].item_label, "1")
        self.assertEqual(document.items[0].item_type, "public_hearing")
        self.assertEqual(document.items[0].section_title, "PUBLIC HEARINGS")
        self.assertIn("Florence-Firestone", document.items[0].title)

    def test_extracts_bos_set_matter_without_merging_section_boilerplate(self) -> None:
        sample_text = """
        STATEMENT OF PROCEEDINGS FOR THE
        REGULAR MEETING OF THE BOARD OF SUPERVISORS
        Tuesday, August 5, 2025

        I. SET MATTERS
        Set Matter 1. Report on the County's Budget
        Report by the Chief Executive Officer on the County's budget. (25-4327)
        Attachments:
        Presentation

        II. CONSENT CALENDAR
        All matters are approved by one motion unless held.
        2. Motion to Establish a Reward in the Amount of $20,000. (25-3665)
        On motion of Supervisor Mitchell, seconded by Supervisor Hahn, this item was duly carried.
        """
        document = extract_agenda_items_from_text_path(
            self._write_temp_fixture("bos_set_matter_and_consent_sample.txt", sample_text),
            parser_name="la_county_bos_sop_text",
        )

        self.assertEqual(document.item_count, 2)
        self.assertEqual(document.items[0].item_label, "1")
        self.assertEqual(document.items[0].section_title, "SET MATTERS")
        self.assertIn("County's Budget", document.items[0].title)
        self.assertEqual(document.items[1].motion_by, "Mitchell")
        self.assertEqual(document.items[1].second_by, "Hahn")
        self.assertEqual(document.items[1].final_action, "approved")
        self.assertEqual(document.items[1].item_label, "2")
        self.assertEqual(document.items[1].section_title, "CONSENT CALENDAR")

    def test_extracts_regional_homeless_alignment_items(self) -> None:
        path = self.repo_root / "tests" / "fixtures" / "regional_homeless_alignment_sample.txt"
        document = extract_agenda_items_from_text_path(path)

        self.assertEqual(document.cluster_name, "Los Angeles County Leadership Table For Regional Homeless Alignment")
        self.assertEqual(document.meeting_date, "Thursday, June 5, 2025")
        self.assertEqual(document.meeting_date_iso, "2025-06-05")
        self.assertEqual(document.item_count, 5)
        self.assertEqual(document.items[0].section_title, "ADMINISTRATIVE MATTERS")
        self.assertEqual(document.items[0].item_label, "1")
        self.assertEqual(document.items[0].item_type, "brown_act_agenda_item")
        self.assertIn("Measure A Implementation", document.items[3].text_block)

    def test_strips_cluster_boilerplate_and_header_lines_from_county_items(self) -> None:
        sample_text = """
        Board of Supervisors
        Members of the Public may address the Family & Social Services Cluster
        DATE: May 20, 2026

        1. INFORMATIONAL ITEM(S):
        A. Fire Recovery Update
        Agenda Posted: May 15, 2026
        Supporting Documentation: Available upon request
        """
        document = extract_agenda_items_from_text_path(
            self._write_temp_fixture("cluster_boilerplate_sample.txt", sample_text)
        )

        self.assertEqual(document.cluster_name, "Family & Social Services Cluster")
        self.assertEqual(document.item_count, 1)
        self.assertEqual(document.items[0].title, "Fire Recovery Update")
        self.assertNotIn("Agenda Posted", document.items[0].text_block)
        self.assertNotIn("Supporting Documentation", document.items[0].text_block)

    def test_strips_regional_alignment_body_boilerplate(self) -> None:
        sample_text = """
        AGENDA FOR THE REGULAR MEETING OF THE
        Los Angeles County Executive Committee For Regional Homeless Alignment
        Best Practices For Standardization Of Care Committee
        Los Angeles Homeless Services Authority
        637 Wilshire Boulevard 1st Floor Commission Room
        Thursday, September 18, 2025, 12:00 P.M.
        Participate Via Computer Or Smartphone

        I. ADMINISTRATIVE MATTERS
        1. Measure A Implementation
        """
        document = extract_agenda_items_from_text_path(
            self._write_temp_fixture("regional_alignment_boilerplate_sample.txt", sample_text)
        )

        self.assertEqual(
            document.cluster_name,
            "Los Angeles County Executive Committee For Regional Homeless Alignment Best Practices For Standardization Of Care Committee",
        )
        self.assertEqual(document.item_count, 1)
        self.assertEqual(document.items[0].title, "Measure A Implementation")

    def test_extracts_supporting_document_minutes_with_role_and_votes(self) -> None:
        sample_text = """
        Friday, February 13, 2026
        DRAFT STATEMENT OF PROCEEDINGS
        FOR THE SPECIAL MEETING OF THE
        LOS ANGELES COUNTY EXECUTIVE COMMITTEE FOR
        REGIONAL HOMELESS ALIGNMENT

        3. Approval of the December 12, 2025, ECRHA Special Meeting Minutes.
        On motion of Member Lindsey P. Horvath, seconded by Member Hafsa Kaka, duly carried by the following vote, this item was approved:
        Ayes: Board Member Lindsey P. Horvath, Board Member Hafsa Kaka
        Absent: Board Member Kathryn Barger
        """
        path = self._write_temp_supporting_fixture(
            "supporting_001_minutes.txt",
            sample_text,
            body_slug="executive-committee-for-regional-homeless-alignment",
        )
        document = extract_agenda_items_from_text_path(path)

        self.assertEqual(document.document_role, "minutes")
        self.assertEqual(
            document.cluster_name,
            "Los Angeles County Executive Committee For Regional Homeless Alignment",
        )
        self.assertEqual(document.meeting_date_iso, "2026-02-13")
        self.assertEqual(document.items[0].document_role, "minutes")
        self.assertEqual(document.items[0].motion_by, "Member Lindsey P. Horvath")
        self.assertEqual(document.items[0].second_by, "Member Hafsa Kaka")
        self.assertEqual(document.items[0].final_action, "approved")

    def test_extracts_supporting_document_governance_doc_role(self) -> None:
        sample_text = """
        LEADERSHIP TABLE
        LTRHA Membership:
        Update & Recommendations
        Membership Subcommittee
        In order to facilitate a fair and transparent process to fill vacant seats, the LTRHA Bylaws specify:
        """
        path = self._write_temp_supporting_fixture(
            "supporting_007_214150.txt",
            sample_text,
            body_slug="leadership-table-for-regional-homeless-alignment",
        )
        document = extract_agenda_items_from_text_path(path)

        self.assertEqual(document.document_role, "governance_doc")
        self.assertEqual(
            document.cluster_name,
            "Leadership Table For Regional Homeless Alignment",
        )
        self.assertEqual(document.items[0].item_type, "supporting_governance_doc")

    def _write_temp_fixture(self, name: str, content: str) -> Path:
        tmp_dir = self.repo_root / "local" / "tmp_item_extraction_tests"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        path = tmp_dir / name
        path.write_text(content.strip(), encoding="utf-8")
        return path

    def _write_temp_supporting_fixture(self, name: str, content: str, body_slug: str) -> Path:
        tmp_dir = (
            self.repo_root
            / "local"
            / "tmp_item_extraction_tests"
            / "2026-01-01"
            / body_slug
            / "supporting_docs"
        )
        tmp_dir.mkdir(parents=True, exist_ok=True)
        path = tmp_dir / name
        path.write_text(content.strip(), encoding="utf-8")
        return path
