"""SEC EDGAR data collector for 13F filings and Form 4 insider trades.

SEC EDGAR API Documentation: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
Rate limit: 10 requests per second
No API key required - just need to identify yourself via User-Agent header.
"""

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from xml.etree import ElementTree as ET

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from ..utils.config import settings
from ..utils.logger import get_logger
from ..utils.rate_limiter import RateLimiter

logger = get_logger(__name__)


@dataclass
class Filing13F:
    """Represents a 13F quarterly holding."""

    cik: str
    institution_name: str
    report_date: datetime
    filed_date: datetime
    cusip: str
    company_name: str
    shares: int
    value_usd: int  # In thousands
    security_type: str  # SH, PUT, CALL


@dataclass
class Form4Filing:
    """Represents a Form 4 insider trade."""

    accession_number: str
    issuer_cik: str
    issuer_name: str
    ticker: str
    insider_cik: str
    insider_name: str
    insider_title: str
    is_director: bool
    is_officer: bool
    is_ten_percent_owner: bool
    transaction_type: str  # P=Purchase, S=Sale
    trade_date: datetime
    filed_date: datetime
    shares: int
    price_per_share: float
    shares_owned_after: int


class SecEdgarCollector:
    """Collector for SEC EDGAR filings (13F and Form 4).

    Uses the free SEC EDGAR API at data.sec.gov.
    Rate limited to 10 requests/second.
    """

    BASE_URL = "https://data.sec.gov"
    SUBMISSIONS_URL = "https://data.sec.gov/submissions"
    FULL_INDEX_URL = "https://www.sec.gov/cgi-bin/browse-edgar"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": settings.apis.sec_edgar.user_agent,
            "Accept-Encoding": "gzip, deflate",
        })
        self.rate_limiter = RateLimiter(settings.apis.sec_edgar.rate_limit)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _get(self, url: str) -> requests.Response:
        """Make a rate-limited GET request."""
        self.rate_limiter.wait()
        response = self.session.get(url)
        response.raise_for_status()
        return response

    # ==================== Company/Filer Info ====================

    def get_company_submissions(self, cik: str) -> dict:
        """Get all submissions for a company/filer.

        Args:
            cik: Central Index Key (padded to 10 digits)

        Returns:
            JSON data with filer info and recent filings
        """
        cik_padded = cik.zfill(10)
        url = f"{self.SUBMISSIONS_URL}/CIK{cik_padded}.json"

        logger.info(f"Fetching submissions for CIK {cik}")
        response = self._get(url)
        return response.json()

    def get_company_tickers(self) -> dict[str, dict]:
        """Get mapping of CIK to ticker symbols.

        Returns:
            Dict mapping CIK to {ticker, title}
        """
        url = f"{self.BASE_URL}/files/company_tickers.json"
        response = self._get(url)
        data = response.json()

        # Convert to dict keyed by CIK
        result = {}
        for item in data.values():
            cik = str(item["cik_str"])
            result[cik] = {
                "ticker": item["ticker"],
                "title": item["title"],
            }
        return result

    # ==================== 13F Filings ====================

    def get_recent_13f_filers(self, days_back: int = 7) -> list[dict]:
        """Get list of institutions that recently filed 13F.

        Uses the SEC's full-text search to find recent 13F filings.
        """
        # SEC EDGAR search for recent 13F-HR filings
        url = "https://efts.sec.gov/LATEST/search-index"
        params = {
            "q": "13F-HR",
            "dateRange": "custom",
            "startdt": (datetime.now().date().isoformat()),
            "enddt": (datetime.now().date().isoformat()),
            "forms": "13F-HR",
        }

        # Alternative: Use the daily index files
        # For simplicity, we'll use the submissions API to check known filers

        logger.info("Fetching recent 13F filers")
        # This is a simplified approach - in production, you'd parse the daily index
        return []

    def get_13f_holdings(self, cik: str, report_date: Optional[str] = None) -> list[Filing13F]:
        """Get 13F holdings for an institution.

        Args:
            cik: Institution's CIK number
            report_date: Optional quarter end date (YYYY-MM-DD)

        Returns:
            List of holdings from the 13F filing
        """
        submissions = self.get_company_submissions(cik)

        # Find 13F-HR filings
        filings = submissions.get("filings", {}).get("recent", {})
        form_types = filings.get("form", [])
        accession_numbers = filings.get("accessionNumber", [])
        filing_dates = filings.get("filingDate", [])

        holdings = []

        for i, form_type in enumerate(form_types):
            if form_type == "13F-HR":
                accession = accession_numbers[i].replace("-", "")
                filed_date = filing_dates[i]

                # Fetch the actual 13F data
                try:
                    filing_holdings = self._parse_13f_filing(cik, accession)
                    for h in filing_holdings:
                        h.filed_date = datetime.strptime(filed_date, "%Y-%m-%d")
                    holdings.extend(filing_holdings)
                except Exception as e:
                    logger.error(f"Error parsing 13F for {cik}: {e}")

                # Only get most recent filing unless date specified
                if not report_date:
                    break

        return holdings

    def _parse_13f_filing(self, cik: str, accession: str) -> list[Filing13F]:
        """Parse a 13F-HR filing XML to extract holdings."""
        cik_padded = cik.zfill(10)
        # Try to find the infotable XML file
        index_url = f"https://www.sec.gov/Archives/edgar/data/{cik_padded}/{accession}/index.json"

        try:
            response = self._get(index_url)
            index_data = response.json()
        except Exception:
            logger.warning(f"Could not fetch index for {cik}/{accession}")
            return []

        # Find the XML file with holdings
        xml_file = None
        for item in index_data.get("directory", {}).get("item", []):
            name = item.get("name", "")
            if "infotable" in name.lower() and name.endswith(".xml"):
                xml_file = name
                break

        if not xml_file:
            return []

        # Fetch and parse the XML
        xml_url = f"https://www.sec.gov/Archives/edgar/data/{cik_padded}/{accession}/{xml_file}"
        response = self._get(xml_url)

        return self._parse_13f_xml(response.text, cik)

    def _parse_13f_xml(self, xml_content: str, cik: str) -> list[Filing13F]:
        """Parse 13F XML content."""
        holdings = []

        # Remove namespace for easier parsing
        xml_content = re.sub(r'\sxmlns="[^"]+"', '', xml_content)

        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            logger.error(f"XML parse error: {e}")
            return []

        for info in root.findall(".//infoTable"):
            try:
                cusip = info.findtext("cusip", "").strip()
                name = info.findtext("nameOfIssuer", "").strip()
                shares_elem = info.find(".//sshPrnamt")
                value_elem = info.find("value")

                shares = int(shares_elem.text) if shares_elem is not None and shares_elem.text else 0
                value = int(value_elem.text) if value_elem is not None and value_elem.text else 0

                # Get security type (SH, PUT, CALL)
                shrs_type = info.findtext(".//sshPrnamtType", "SH")

                holdings.append(Filing13F(
                    cik=cik,
                    institution_name="",  # Fill later
                    report_date=datetime.now(),  # Fill from filing
                    filed_date=datetime.now(),
                    cusip=cusip,
                    company_name=name,
                    shares=shares,
                    value_usd=value,
                    security_type=shrs_type,
                ))
            except Exception as e:
                logger.warning(f"Error parsing holding: {e}")
                continue

        return holdings

    # ==================== Form 4 (Insider Trading) ====================

    def get_recent_form4_filings(self, ticker: Optional[str] = None, days_back: int = 7) -> list[Form4Filing]:
        """Get recent Form 4 insider trading filings.

        Args:
            ticker: Optional ticker to filter by
            days_back: Number of days to look back

        Returns:
            List of Form 4 filings
        """
        filings = []

        # Use SEC full-text search API
        search_url = "https://efts.sec.gov/LATEST/search-index"

        # For simplicity, we'll use the RSS feed approach
        rss_url = "https://www.sec.gov/cgi-bin/browse-edgar"
        params = {
            "action": "getcurrent",
            "type": "4",
            "company": "",
            "dateb": "",
            "owner": "include",
            "count": 100,
            "output": "atom",
        }

        if ticker:
            # First, find the CIK for this ticker
            tickers = self.get_company_tickers()
            cik = None
            for c, info in tickers.items():
                if info["ticker"].upper() == ticker.upper():
                    cik = c
                    break

            if cik:
                params["CIK"] = cik

        try:
            response = self._get(f"{rss_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}")
            # Parse the atom feed
            filings = self._parse_form4_feed(response.text)
        except Exception as e:
            logger.error(f"Error fetching Form 4 filings: {e}")

        return filings

    def _parse_form4_feed(self, content: str) -> list[Form4Filing]:
        """Parse Form 4 RSS/Atom feed."""
        filings = []
        try:
            # Remove namespace for easier parsing
            content = re.sub(r'\sxmlns="[^"]+"', '', content)
            root = ET.fromstring(content)
            
            entries = root.findall("entry")
            logger.info(f"Found {len(entries)} entries in RSS feed")
            
            count = 0
            for entry in entries:
                # Title format: "4 - Company Name (CIK) (Issuer)"
                title = entry.findtext("title", "")
                if not title.startswith("4 ") and not title.startswith("4/A"):
                    continue
                
                link = entry.find("link")
                href = link.get("href") if link is not None else ""
                
                # Extract CIK and Accession from URL
                # https://www.sec.gov/Archives/edgar/data/1067983/000106798324000001/0001067983-24-000001-index.htm
                # We need CIK and Accession
                parts = href.split('/')
                if len(parts) >= 8:
                    cik = parts[6]
                    accession = parts[7].replace('-index.htm', '')
                    
                    # Fetch full details
                    # Rate limit is 10/sec, so this involves I/O
                    try:
                        details = self.get_form4_details(cik, accession)
                        if details:
                            filings.append(details)
                            count += 1
                    except Exception as e:
                        logger.warning(f"Failed to fetch details for {accession}: {e}")
                
                if count >= 30:  # Limit to 30 most recent to keep refresh fast
                    break
                    
        except Exception as e:
            logger.error(f"Error parsing Atom feed: {e}")
            
        return filings

    def get_form4_details(self, cik: str, accession: str) -> Optional[Form4Filing]:
        """Get detailed Form 4 data from SEC.

        Args:
            cik: Company CIK
            accession: Filing accession number

        Returns:
            Parsed Form 4 filing or None
        """
        cik_padded = cik.zfill(10)
        accession_clean = accession.replace("-", "")

        # Fetch the XML
        xml_url = f"https://www.sec.gov/Archives/edgar/data/{cik_padded}/{accession_clean}/{accession}.xml"

        try:
            response = self._get(xml_url)
            return self._parse_form4_xml(response.text, accession)
        except Exception as e:
            logger.error(f"Error fetching Form 4 {accession}: {e}")
            return None

    def _parse_form4_xml(self, xml_content: str, accession: str) -> Optional[Form4Filing]:
        """Parse Form 4 XML content."""
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            logger.error(f"XML parse error: {e}")
            return None

        try:
            # Issuer info
            issuer = root.find(".//issuer")
            issuer_cik = issuer.findtext("issuerCik", "") if issuer else ""
            issuer_name = issuer.findtext("issuerName", "") if issuer else ""
            ticker = issuer.findtext("issuerTradingSymbol", "") if issuer else ""

            # Owner info
            owner = root.find(".//reportingOwner")
            owner_id = owner.find(".//reportingOwnerId") if owner else None
            insider_cik = owner_id.findtext("rptOwnerCik", "") if owner_id else ""
            insider_name = owner_id.findtext("rptOwnerName", "") if owner_id else ""

            relationship = owner.find(".//reportingOwnerRelationship") if owner else None
            is_director = relationship.findtext("isDirector", "0") == "1" if relationship else False
            is_officer = relationship.findtext("isOfficer", "0") == "1" if relationship else False
            is_ten_pct = relationship.findtext("isTenPercentOwner", "0") == "1" if relationship else False
            title = relationship.findtext("officerTitle", "") if relationship else ""

            # Transaction info (get first non-derivative transaction)
            txn = root.find(".//nonDerivativeTransaction")
            if txn is None:
                return None

            txn_date = txn.findtext(".//transactionDate/value", "")
            txn_code = txn.findtext(".//transactionCoding/transactionCode", "")
            shares = txn.findtext(".//transactionAmounts/transactionShares/value", "0")
            price = txn.findtext(".//transactionAmounts/transactionPricePerShare/value", "0")
            shares_after = txn.findtext(".//postTransactionAmounts/sharesOwnedFollowingTransaction/value", "0")

            return Form4Filing(
                accession_number=accession,
                issuer_cik=issuer_cik,
                issuer_name=issuer_name,
                ticker=ticker,
                insider_cik=insider_cik,
                insider_name=insider_name,
                insider_title=title,
                is_director=is_director,
                is_officer=is_officer,
                is_ten_percent_owner=is_ten_pct,
                transaction_type=txn_code,
                trade_date=datetime.strptime(txn_date, "%Y-%m-%d") if txn_date else datetime.now(),
                filed_date=datetime.now(),  # Would get from filing metadata
                shares=int(float(shares)) if shares else 0,
                price_per_share=float(price) if price else 0.0,
                shares_owned_after=int(float(shares_after)) if shares_after else 0,
            )
        except Exception as e:
            logger.error(f"Error parsing Form 4: {e}")
            return None

    # ==================== Bulk Data ====================

    def get_13f_data_set(self, year: int, quarter: int) -> str:
        """Get URL for bulk 13F data set.

        SEC provides quarterly bulk downloads of all 13F data.
        https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets
        """
        return f"https://www.sec.gov/files/structureddata/data/form-13f-data-sets/{year}q{quarter}_form13f.zip"

    # ==================== Notable Filers ====================

    # CIKs of well-known investors to track
    NOTABLE_FILERS = {
        "0001067983": "Berkshire Hathaway (Warren Buffett)",
        "0001336528": "Bridgewater Associates (Ray Dalio)",
        "0001649339": "Citadel Advisors",
        "0001037389": "Renaissance Technologies",
        "0001697748": "Scion Asset Management (Michael Burry)",
        "0001510387": "Tiger Global Management",
        "0001591086": "Pershing Square (Bill Ackman)",
        "0000921669": "Soros Fund Management",
        "0001350694": "Third Point (Dan Loeb)",
        "0001568820": "Viking Global Investors",
    }

    def get_notable_filer_holdings(self) -> dict[str, list[Filing13F]]:
        """Get latest holdings for all notable filers.

        Returns:
            Dict mapping filer name to their holdings
        """
        results = {}

        for cik, name in self.NOTABLE_FILERS.items():
            logger.info(f"Fetching holdings for {name}")
            try:
                holdings = self.get_13f_holdings(cik)
                results[name] = holdings
            except Exception as e:
                logger.error(f"Error fetching {name}: {e}")
                results[name] = []

        return results
