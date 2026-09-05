from rkjo_family.capabilities import capability_names


def test_family_capability_contracts_match_product_architecture() -> None:
    assert capability_names() == (
        "family.management",
        "family.calendar",
        "family.reminder",
        "document.understanding",
        "education.tutoring",
        "family.advice",
    )
