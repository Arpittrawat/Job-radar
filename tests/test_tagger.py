from tagger import tag_title, location_group


def test_specific_tags_win_over_marketing():
    assert tag_title("GTM Engineer") == "GTM engineer"
    assert tag_title("Founder's Office Associate") == "Founder's office"
    assert tag_title("Forward Deployed Engineer") == "FDE"
    assert tag_title("Growth Marketing Associate") == "Growth associate" or tag_title("Growth Marketing Associate") == "Marketing"


def test_marketing_and_no_match():
    assert tag_title("Product Marketing Manager") == "Marketing"
    assert tag_title("Senior Backend Engineer") == ""
    assert tag_title("") == ""


def test_location_groups():
    assert location_group("Bengaluru, India") == "India"
    assert "Remote" in location_group("Remote - Worldwide")
    assert location_group("Berlin") == "Other"
    assert location_group("") == "Other"
