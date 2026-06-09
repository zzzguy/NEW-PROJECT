import unittest

from interview_grouping import create_result, validate_counts


class InterviewGroupingTests(unittest.TestCase):
    def make_rows(self):
        rows = []
        configs = [
            ("본사영업", 84, ["RM", "기업영업", "개인영업", "마케팅"]),
            ("본사지원", 44, ["인사", "재무", "전략", "총무"]),
            ("디지털금융", 48, ["IT", "데이터", "보안", "기획"]),
        ]
        schools = ["A대", "B대", "C대", "D대", "E대", "F대"]
        genders = ["남", "여"]
        applicant_number = 1
        for division, count, jobs in configs:
            for index in range(count):
                rows.append(
                    {
                        "지원부문": division,
                        "지원번호": f"A{applicant_number:04d}",
                        "매칭직무": jobs[index % len(jobs)],
                        "출신학교": schools[(index + applicant_number) % len(schools)],
                        "성별": genders[index % len(genders)],
                    }
                )
                applicant_number += 1
        return rows

    def test_create_result_generates_expected_group_counts(self):
        rows = self.make_rows()
        self.assertEqual(validate_counts(rows, strict=True), [])

        summary_rows, detail_rows, validation_rows = create_result(rows, seed=42)

        self.assertEqual(len(summary_rows), 176)
        self.assertEqual(len({row["조번호"] for row in summary_rows}), 44)
        self.assertEqual(len(validation_rows), 44)
        self.assertEqual({row["인원"] for row in validation_rows}, {4})
        self.assertEqual(len(detail_rows), 176)

    def test_slots_do_not_overlap_within_same_division(self):
        _, detail_rows, _ = create_result(self.make_rows(), seed=42)

        for division in {row["지원부문"] for row in detail_rows}:
            group_slots = {
                (row["조번호"], row["면접일자"], row["면접시간"])
                for row in detail_rows
                if row["지원부문"] == division
            }
            time_slots = {(date, time) for _, date, time in group_slots}
            self.assertEqual(len(group_slots), len(time_slots))


if __name__ == "__main__":
    unittest.main()
