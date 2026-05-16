from src.parser import extract_document_links, is_drug_related


def test_extract_document_links_from_listing_cards():
    html = """
    <div class="view-content">
      <div class="views-row">
        <a href="/en/regulations/123">Regulatory Framework for Drug Approvals</a>
        <span>Drugs</span>
        <time datetime="2024-01-15">15/01/2024</time>
      </div>
      <div class="views-row">
        <a href="/en/food/456">Food Import Rules</a>
        <span>Food</span>
      </div>
    </div>
    """

    records = extract_document_links(
        html,
        source_page="https://www.sfda.gov.sa/en/regulations?tags=2",
        sector="Drugs",
        document_type="Regulation",
    )

    assert len(records) == 1
    assert records[0].title == "Regulatory Framework for Drug Approvals"
    assert records[0].sector == "Drugs"
    assert records[0].page_url == "https://www.sfda.gov.sa/en/regulations/123"
    assert records[0].publication_date == "2024-01-15"


def test_is_drug_related_accepts_domain_terms_and_rejects_food_only():
    assert is_drug_related("Good Review Practices Guideline", "", "Guidelines")
    assert is_drug_related("Regulations and Requirements for Conducting Clinical Trials on Drugs", "", "")
    assert not is_drug_related("Food Import Rules", "Food", "Regulations")


def test_extract_document_links_from_sfda_warning_item_pdf_card():
    html = """
    <article class="warning-item">
      <span class="news-date">2024-06-25</span>
      <div class="custom-tags">
        <a class="inn cat drugs">Drugs</a>
        <a class="inn cat drugs">Procedural rule</a>
      </div>
      <span class="m-c-title">Regulatory Framework for Drugs Approval</span>
      <a href="/sites/default/files/2024-06/RegulatoryFramework_0.pdf" class="download-doc-link">PDF</a>
    </article>
    """

    records = extract_document_links(
        html,
        source_page="https://www.sfda.gov.sa/en/regulations?tags=2",
        sector="Drugs",
        document_type="Regulation",
    )

    assert len(records) == 1
    assert records[0].title == "Regulatory Framework for Drugs Approval"
    assert records[0].document_type == "Procedural rule"
    assert records[0].publication_date == "2024-06-25"
    assert records[0].pdf_url == "https://www.sfda.gov.sa/sites/default/files/2024-06/RegulatoryFramework_0.pdf"
    assert records[0].page_url.startswith("https://www.sfda.gov.sa/en/regulations?tags=2#")


def test_multisector_tag_is_not_used_as_document_type():
    html = """
    <article class="warning-item">
      <span class="news-date">2026-04-01</span>
      <div class="custom-tags">
        <a class="inn cat drugs">Food, Drugs, Medical Devices</a>
      </div>
      <span class="m-c-title">Requirements for Clearance of Medicines</span>
      <a href="/sites/default/files/example.pdf" class="download-doc-link">PDF</a>
    </article>
    """

    records = extract_document_links(html, "https://www.sfda.gov.sa/en/regulations?tags=2", "Drugs", "Regulation")

    assert records[0].document_type == "Regulation"
