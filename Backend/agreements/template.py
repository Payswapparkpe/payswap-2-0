from django.utils import timezone

from merchants.models import Merchant
from merchants.privacy import decrypt_step_data
from verification.models import BankAccount

TEMPLATE_VERSION = "voucher-supply-2"

FIRST_PARTY = {
    "legal_name": "PAYSWAP FINTECH PRIVATE LIMITED",
    "office": ("4TH, C-24 A, PANKAJ SINGHVI MARG, LAL KOTHI, Jaipur, Rajasthan, 302015, India"),
    "signatory_name": "ABHISHEK BANSAL",
    "signatory_designation": "CGO",
    "email": "Abhishek@payswap.in",
    "short_name": "Payswap",
}

VERIFICATION_REQUIRED_MESSAGE = (
    "The voucher supply agreement can be issued and digitally signed only after "
    "KYC, KYB, and bank verification succeed."
)


def _entity_clause(merchant: Merchant) -> str:
    mapping = {
        Merchant.EntityType.INDIVIDUAL: "an individual",
        Merchant.EntityType.PROPRIETORSHIP: "a proprietorship concern",
        Merchant.EntityType.PARTNERSHIP: "a partnership firm",
        Merchant.EntityType.LLP: "a limited liability partnership incorporated under the Limited Liability Partnership Act, 2008",
        Merchant.EntityType.PRIVATE_LIMITED: "a company incorporated under the Companies Act, 2013",
        Merchant.EntityType.PUBLIC_LIMITED: "a public company incorporated under the Companies Act, 2013",
        Merchant.EntityType.TRUST: "a trust",
        Merchant.EntityType.SOCIETY: "a society",
        Merchant.EntityType.HUF: "a Hindu Undivided Family",
    }
    return mapping.get(merchant.entity_type, "a business entity")


def _step_data(merchant: Merchant, key: str) -> dict:
    application = merchant.applications.order_by("-created_at").first()
    if application is None:
        return {}
    step = application.steps.filter(key=key).first()
    # Agreements are legal documents: they require the decrypted identifiers.
    return decrypt_step_data(step.data) if step else {}


def verification_complete(merchant: Merchant) -> bool:
    verified = Merchant.VerificationState.VERIFIED
    return (
        merchant.kyc_status == verified
        and merchant.kyb_status == verified
        and merchant.bank_status == verified
    )


def verification_blockers(merchant: Merchant) -> list[str]:
    blockers = []
    if merchant.kyc_status != Merchant.VerificationState.VERIFIED:
        blockers.append(f"KYC is {merchant.get_kyc_status_display()}")
    if merchant.kyb_status != Merchant.VerificationState.VERIFIED:
        blockers.append(f"KYB is {merchant.get_kyb_status_display()}")
    if merchant.bank_status != Merchant.VerificationState.VERIFIED:
        blockers.append(f"Bank is {merchant.get_bank_status_display()}")
    return blockers


def merchant_party_context(merchant: Merchant) -> dict:
    business = _step_data(merchant, "business")
    owners = _step_data(merchant, "owners")
    kyc = _step_data(merchant, "kyc")
    kyb = _step_data(merchant, "kyb")
    bank = _step_data(merchant, "bank")
    owner = merchant.owner
    legal_name = business.get("legal_name") or merchant.business_name or owner.name or owner.email
    office = (
        business.get("registered_office")
        or business.get("address")
        or owners.get("address")
        or f"As declared in merchant application {merchant.public_id}"
    )
    pincode = (business.get("pincode") or "").strip()
    if pincode and pincode not in office:
        office = f"{office}, {pincode}"
    people = list(owners.get("people") or [])
    signatory_row = next((row for row in people if row.get("signatory")), people[0] if people else {})
    signatory = (
        owners.get("authorized_signatory")
        or owners.get("owner_name")
        or signatory_row.get("name")
        or owner.name
        or owner.email
    )
    designation = owners.get("designation") or signatory_row.get("designation") or "Authorized Signatory"
    beneficial = (
        merchant.owners.filter(is_authorized_signatory=True).first() or merchant.owners.order_by("id").first()
    )
    if beneficial:
        signatory = beneficial.full_name or signatory
        designation = beneficial.role or designation
    ownership = owners.get("ownership_percent") or signatory_row.get("percent") or ""
    if beneficial and beneficial.ownership_percent is not None:
        ownership = str(beneficial.ownership_percent)
    bank_holder = bank.get("account_holder") or ""
    bank_ifsc = bank.get("ifsc") or ""
    bank_last4 = ""
    account = BankAccount.objects.filter(merchant=merchant).first()
    if account:
        bank_holder = account.account_holder or bank_holder
        bank_ifsc = account.ifsc or bank_ifsc
        number = account.get_account_number() or ""
        bank_last4 = number[-4:] if number else ""
    return {
        "merchant_id": merchant.public_id,
        "legal_name": legal_name,
        "entity_clause": _entity_clause(merchant),
        "entity_type": merchant.get_entity_type_display(),
        "office": office,
        "signatory_name": signatory,
        "signatory_designation": designation,
        "email": owner.email,
        "mobile": owner.mobile or "Not provided",
        "pan": business.get("pan") or kyc.get("pan") or "As verified",
        "gstin": business.get("gstin") or kyb.get("gstin") or "As verified",
        "cin": business.get("cin") or business.get("llpin") or kyb.get("cin") or "Not applicable",
        "ownership": ownership or "As declared",
        "kyc_status": merchant.get_kyc_status_display(),
        "kyb_status": merchant.get_kyb_status_display(),
        "bank_status": merchant.get_bank_status_display(),
        "bank_holder": bank_holder or "As verified",
        "bank_ifsc": bank_ifsc or "As verified",
        "bank_last4": bank_last4 or "As verified",
    }


def render_voucher_supply_agreement(merchant: Merchant) -> tuple[str, dict]:
    second = merchant_party_context(merchant)
    first = FIRST_PARTY
    effective = timezone.localdate().strftime("%d %B %Y")
    snapshot = {
        "first_party": first,
        "second_party": second,
        "effective_date": effective,
        "title": "AGREEMENT FOR SUPPLY OF BRAND VOUCHERS & GIFT CARDS",
        "template_version": TEMPLATE_VERSION,
    }
    body = AGREEMENT_TEXT.format(
        effective_date=effective,
        first_legal_name=first["legal_name"],
        first_office=first["office"],
        first_signatory_name=first["signatory_name"],
        first_signatory_designation=first["signatory_designation"],
        first_email=first["email"],
        second_legal_name=second["legal_name"],
        second_entity_clause=second["entity_clause"],
        second_office=second["office"],
        second_signatory_name=second["signatory_name"],
        second_signatory_designation=second["signatory_designation"],
        second_email=second["email"],
        second_mobile=second["mobile"],
        merchant_id=second["merchant_id"],
        pan=second["pan"],
        gstin=second["gstin"],
        cin=second["cin"],
        entity_type=second["entity_type"],
        ownership=second["ownership"],
        kyc_status=second["kyc_status"],
        kyb_status=second["kyb_status"],
        bank_status=second["bank_status"],
        bank_holder=second["bank_holder"],
        bank_ifsc=second["bank_ifsc"],
        bank_last4=second["bank_last4"],
    )
    return body, snapshot


AGREEMENT_TEXT = """AGREEMENT FOR SUPPLY OF BRAND VOUCHERS & GIFT CARDS

This Agreement ("Agreement") is executed on {effective_date} ("Effective Date")

BY AND BETWEEN

{first_legal_name}, a company incorporated under the Companies Act, 2013, having its registered office at {first_office}, duly represented by its authorized signatory (hereinafter referred to as "Payswap" or "Supplier" or "First Party", which expression shall unless repugnant to the context include its successors and permitted assigns);

AND

{second_legal_name}, {second_entity_clause}, having its principal place of business / registered office at {second_office}, Merchant ID {merchant_id}, PAN {pan}, GSTIN {gstin}, CIN/LLPIN {cin}, entity type {entity_type}, duly represented by its authorized signatory (hereinafter referred to as "Merchant" or "Buyer" or "Second Party", which expression shall unless repugnant to the context include its successors and permitted assigns).

Payswap and Merchant are hereinafter individually referred to as a "Party" and collectively as the "Parties."

The First Party is Payswap. The Second Party is the Merchant. Particulars of the Merchant in Schedule B are prefilled from verified KYC, KYB, and bank records. Payswap agrees to supply Gift Cards/Vouchers to the Merchant on the terms below. This Agreement is issued only after KYC/KYB/bank verification succeed, and the Merchant shall execute it solely by Aadhaar eSign.

1. DEFINITIONS
1.1 Gift Cards / Vouchers
Means digital or physical brand gift cards, vouchers, e-codes, or similar instruments issued by third-party brands including but not limited to Amazon, Flipkart, Myntra, and other brands made available by Payswap.

1.2 Order
Means a written request raised by Merchant through the authenticated merchant portal, registered email IDs, or any other mode approved by Payswap.

1.3 Applicable Laws
Includes all Indian laws, rules, regulations, RBI guidelines, PMLA, FEMA, and any statutory or regulatory framework applicable from time to time.

1.4 Lien / Debit Freeze
Means any restriction, attachment, or hold imposed by any bank, regulatory, law enforcement, or governmental authority.

1.5 Activation Failure
Means a voucher that fails to activate, transmit, or function due to technical defect, expired inventory, brand rejection, or Supplier error, as determined by mutually agreed testing protocol.

1.6 SLA (Service Level Agreement)
Means the performance standards and timelines defined in Schedule A for voucher delivery, activation, and replacement.

1.7 Business Day
Means Monday to Friday, excluding Indian national holidays and RBI gazetted holidays.

2. SCOPE OF AGREEMENT
2.1 Principal-to-Principal Basis
Payswap agrees to supply Gift Cards/Vouchers to Merchant strictly on a principal-to-principal basis, subject to this Agreement and in compliance with all Applicable Laws.

2.2 Brand Terms Acknowledgment
Merchant acknowledges that Gift Cards/Vouchers are governed by the respective brand terms. Payswap shall notify Merchant of any material change, suspension, or restriction imposed by issuing brands within 24 hours of becoming aware, and shall provide commercially reasonable assistance to Merchant in managing such restrictions.

2.3 No Partnership
Nothing in this Agreement creates any partnership, agency, joint venture, or fiduciary relationship.

3. ORDERING & DELIVERY
3.1 Order Binding Nature
All Orders placed by Merchant and accepted by Payswap shall be binding.

3.2 Advance Payment Requirement
Delivery shall be strictly subject to receipt of 100% advance payment cleared in Payswap's bank account. Upon receipt of cleared payment, Payswap shall issue an Order Confirmation specifying the delivery timeline per Section 3.3 below.

3.3 Delivery Timelines
Payswap shall deliver vouchers according to the following timelines:
(a) Electronic Vouchers (e-vouchers):
- Same-day delivery: Standard timeline for e-vouchers ordered before 2:00 PM IST on any Business Day
- T+1 delivery: In exceptional circumstances (brand delays, technical issues, or order complexity) with prior notice to Merchant and 50% service credit if deadline missed
- Failed e-vouchers: Any e-voucher that fails to activate within 24 hours of delivery shall be immediately replaced by Supplier at no cost to Merchant (see Section 3.4)
(b) Physical Vouchers / Gift Cards:
- T+3 delivery: Physical vouchers shall be dispatched within 3 Business Days of cleared payment
- Tracking: Supplier shall provide tracking reference within 24 hours of dispatch
- Failed physical vouchers: Any physical voucher undelivered beyond T+5 or received in non-functional state shall be immediately replaced by Supplier at no cost to Merchant
Failure to meet these timelines shall trigger:
- Immediate refund of the full order amount if delivery is not completed within 7 days of scheduled delivery date, upon Merchant's request
- Delay interest: At the rate of 36% per annum, calculated from the scheduled delivery date until actual delivery or refund, whichever is earlier
- Merchant's right to cancel: Without penalty, if timeline is breached by more than 3 Business Days

3.4 Replacement Obligation for Defective/Non-Activating Vouchers
Payswap shall immediately replace, at its own cost, any voucher that:
- Fails to activate within 24 hours of delivery due to technical defect, expiration, or inventory unavailability
- Is rejected by the issuing brand due to error in Supplier's systems or inventory management
- Is non-functional or partially redeemable due to Supplier error or negligence
- Does not match the denomination or terms specified in the Order Confirmation
Replacement Process:
1. Merchant shall notify Supplier within 7 days of discovering the defect; Supplier shall investigate and confirm defect status within 2 Business Days
2. Replacement vouchers of equivalent value shall be delivered within 2 Business Days of confirmation
3. If replacement is not possible due to brand discontinuation or supply shortage, Supplier shall refund the full amount within 3 Business Days

3.5 Refund Scenarios
Payswap shall refund Merchant's payment in full within 3 Business Days in the following cases:
1. Activation Failure: Voucher fails to activate after 2 replacement attempts
2. Brand Cancellation or Discontinuation: Issuing brand withdraws the voucher product during the validity period, preventing redemption
3. Undelivered Vouchers: Physical or electronic vouchers not delivered by the SLA deadline (T+1 for e-vouchers, T+5 for physical)
4. Partial Refund: If a batch order is only partially fulfilled and Merchant requests refund for the unfulfilled portion because of delay
5. Merchant's Request: Upon written request, subject to confirmation that the order is unused/undelivered
6. Regulatory/AML Hold: If a Lien or Debit Freeze prevents delivery (see Section 5) and remains unresolved for more than 14 days
Refunds shall be processed to the same payment method or account from which funds originated, without deduction of any charges or fees.

3.6 Delivery Completion
Delivery shall be deemed complete only when:
- (Electronic): Voucher code is transmitted to Merchant and subsequently activates successfully within 24 hours
- (Physical): Physical voucher is received by Merchant in verified functional condition
Until such verification, risk of loss remains with Supplier.

3.7 Discrepancy Reporting Window
Merchant shall report discrepancies, if any, within 7 days of delivery, covering activation failures, partial redemption, incorrect denominations, or brand-level blocks. Failure to report within 7 days shall result in Merchant retaining the right to claim replacement or refund up to 30 days post-delivery if defects are discovered through reasonable use. Delivery shall NOT be deemed accepted merely due to non-reporting; acceptance requires actual successful activation and use.

4. PAYMENT TERMS
4.1 Advance Payment Requirement
Merchant shall make 100% advance payment for each Order. Payswap shall not process any Order until cleared funds are received in its designated bank account.

4.2 No Credit or Deferred Payment
No credit, deferred payment, or overdraft shall be provided unless expressly agreed in writing by Payswap and Merchant (including specific repayment schedule and interest terms).

4.3 Suspension / Rejection of Orders
Payswap reserves the right to suspend or reject Orders in case of chargebacks (if substantiated), disputes (with written evidence), suspicious transactions (with notice and opportunity to respond), or compliance concerns. Grounds for suspension shall be objectively documented and communicated to Merchant in writing within 24 hours. Merchant shall have 5 Business Days to respond or cure the concern before Orders are rejected.

4.4 Non-Refundability
Payments are non-refundable, EXCEPT in Activation Failure after 2 replacement attempts; undelivered within SLA; brand withdrawal; regulatory hold beyond 14 days without Merchant's fault; Merchant termination for cause if Supplier materially breaches; or force majeure preventing delivery beyond 21 days. Refunds shall be processed within 3 Business Days of Supplier's acceptance of the refund claim, without deduction of service charges, processing fees, or commissions.

5. SOURCE OF FUNDS & AML COMPLIANCE
5.1 Merchant's Representations and Warranties
Merchant represents and warrants that all funds used are from legitimate, lawful, and verifiable sources; Merchant and its beneficial owners are not on any sanctions list or PEP list; Merchant shall comply with AML, KYC, and CFT requirements; and Merchant shall provide accurate KYC/KYB documentation as prescribed by Supplier.

5.2 Supplier's Limited AML Obligation
Payswap shall NOT be responsible or liable for violations of PMLA, FEMA, RBI or other regulatory guidelines EXCEPT where such violation arises directly from Payswap's own negligence, willful misconduct, or breach of its AML compliance procedures.

5.3 Notification and Cooperation
If Payswap's banking relationships or processes (not Merchant's conduct) trigger regulatory scrutiny, Payswap shall notify Merchant in writing within 24 hours of any Lien, Debit Freeze, or regulatory inquiry affecting Merchant's account or transaction; provide written details of the authority, grounds, and timeframe; and shall NOT unilaterally withhold delivery without first providing Merchant 5 Business Days' notice and opportunity to respond.

5.4 Cure Period
If the hold arises from Supplier's own account issues and NOT from Merchant's actual non-compliance, Supplier shall cooperate to resolve the issue within 14 days, provide a written status update every 3 Business Days, and if unresolved beyond 14 days, refund Merchant's payment in full.

5.5 Mutual Obligation for Regulatory Costs
If regulatory inquiry arises from Merchant's use of vouchers in violation of law or brand policy, Merchant shall reimburse Supplier's reasonable legal fees related to such inquiry and vice versa. If inquiry arises from Supplier's systems, banking relationships, or failure to maintain AML procedures, Supplier shall bear its own costs.

5.6 Withholding Liability
If Supplier withholds delivery or suspends transactions, Supplier shall have liability for interest at 36% per annum on withheld amounts from the withholding date, and consequential losses if withholding is later determined to be without reasonable cause.

5.7 Right to Terminate (Limited to Material AML Breach)
In case of a confirmed, material AML violation attributable to Merchant, Supplier may terminate this Agreement upon 5 Business Days' written notice and opportunity for Merchant to cure or respond.

6. PROHIBITED USE & RESTRICTIONS
6.1 Prohibited Activities
Merchant shall not list or resell vouchers on public marketplaces; use vouchers for crypto, betting, gaming, money laundering, or other restricted categories as defined by RBI or brand policies; sell or distribute vouchers outside India without prior written consent; or misrepresent the source or use of vouchers.

6.2 Permitted Uses
Notwithstanding Section 6.1, Merchant may lawfully distribute vouchers to employees as benefits or rewards; to customers as loyalty or promotional gifts (closed-user group); use vouchers within internal corporate platforms owned or controlled by Merchant; distribute through Merchant's authorized reseller or franchise network if compliant with brand terms; and use vouchers for any lawful purpose not prohibited by Applicable Laws or brand terms.

6.3 Post-Delivery Responsibility
Merchant assumes full responsibility post-delivery for safe custody and compliant usage of vouchers, and shall indemnify Supplier for Merchant's misuse.

6.4 Definition of "Misuse"
"Misuse" means actual use of vouchers in violation of Applicable Laws or brand terms, or actual resale on public marketplaces. Mere compliance inquiries shall not constitute misuse.

7. FORFEITURE RIGHTS
7.1 Forfeiture Grounds (Limited and Objective)
Payswap may forfeit paid or outstanding amounts ONLY in case of confirmed material breach (substantiated violation of Applicable Laws or brand terms), false declaration in KYC/KYB, or confirmed AML violation. Forfeiture shall NOT apply to inquiries where no wrongdoing is found, brand policy changes not caused by Merchant's breach, or disagreements about permitted use.

7.2 Forfeiture Process
Prior to forfeiture, Payswap shall provide written notice with documentary evidence; grant Merchant 10 Business Days to respond or cure; consider Merchant's response in good faith; limit forfeiture to the amount directly linked to the confirmed violation; and permit escalation to a senior executive of Supplier if Merchant contests.

7.3 Final Determination
After the cure period, if Supplier determines forfeiture is justified, Supplier shall provide written final notice with reasons. Forfeiture shall be contestable through dispute resolution and arbitration.

8. INDEMNITY & LIABILITY
8.1 Merchant's Indemnity
Merchant shall indemnify, defend, and hold harmless Payswap from claims, penalties, losses, investigations, or damages arising from Merchant's proven breach; misuse by Merchant or Merchant's personnel attributable to Merchant's negligence or willful conduct; false representation in KYC/KYB; or regulatory action resulting from Merchant's conduct. Merchant shall NOT indemnify Supplier for Supplier's own negligence or willful misconduct; brand-level policy changes; regulatory action from Supplier's failure to maintain AML procedures; or Merchant's permitted uses under Section 6.2.

8.2 Supplier's Liability
Payswap shall NOT be liable for indirect or consequential losses, or brand-level restrictions beyond Supplier's control. Payswap SHALL be liable for direct loss caused by failure to deliver within SLA; non-replacement of defective vouchers after 2 attempts; unwarranted withholding due to Supplier error; or breach of confidentiality. Supplier's liability shall be capped at the lesser of the actual documented direct loss or three months' average fees from Merchant's orders or the outstanding order amount in question.

8.3 Supplier's Obligation to Assist in Brand Disputes
If an issuing brand imposes restrictions on Merchant's account or disputes redemption, Supplier shall provide commercially reasonable assistance including investigation, representation to the brand, escalation, and provision of transaction records.

9. TERMINATION
9.1 Supplier's Termination Right
Payswap may terminate this Agreement ONLY upon material breach (with 5 Business Days' notice and cure opportunity), a regulatory or judicial order requiring cessation of transaction with Merchant, or substantiated AML red flag (with 5 Business Days' notice). Payswap may NOT terminate immediately without notice for inquiries without final determination, disagreements about permitted use, or mere suspicion without evidence.

9.2 Merchant's Termination Right
Merchant may terminate this Agreement by providing 7 days' prior written notice and settling all dues, including for outstanding orders placed.

9.3 Termination for Supplier's Material Breach
Merchant may terminate with immediate effect if Supplier fails to deliver 50% or more of a large order (INR 5 Lakhs+) within 7 days of the SLA deadline; fails to refund amounts due under Section 4.4 within 10 days of Merchant's request; or materially breaches confidentiality or misuses Merchant's data.

9.4 Effect of Termination
Upon termination: unfulfilled orders shall be completed or refunded per this clause; unused credit balances refunded within 5 Business Days; confidentiality survives indefinitely; indemnity, liability limitations, confidentiality, and dispute resolution survive. Merchant may terminate for convenience on 30 days' written notice; unused advances shall be refunded within 7 days subject to documented costs incurred for that specific order, if any.

10. FORCE MAJEURE
Neither Party shall be liable for failure to perform due to events beyond reasonable control including natural disasters, war, government action, pandemic as declared by WHO or Government of India, failure of internet/power/telecom not caused by the Party, or brand-level discontinuation. Force majeure does NOT include market-driven price changes, brand policy amendments, or Supplier's financial distress unless caused by a declared event. The affected Party shall notify the other within 24 hours. If performance is impaired for more than 14 days, either Party may terminate without liability, provided the other Party is offered extension, partial delivery, or refund. Both Parties shall use commercially reasonable efforts to mitigate and resume performance.

11. CONFIDENTIALITY
All commercial, technical, transactional, and financial information shared by either Party shall be treated as confidential. Permitted disclosures: to regulators as required by law; to employees or advisors bound by confidentiality; to enforce rights under this Agreement. Confidentiality survives termination indefinitely. Supplier shall comply with applicable data protection laws and shall not sell, trade, or monetize Merchant's personal or transaction data without consent.

12. SERVICE LEVEL AGREEMENT & SUPPORT
Payswap shall maintain the delivery and replacement timelines in Schedule A. Supplier shall provide a monthly SLA compliance report within 10 days of month-end. Service credits: 1-3 days late 2% of order value credited; 4-7 days late 5% refunded; beyond 7 days full refund or cancellation at Merchant's election. Email support response within 4 hours on Business Days. Monthly reconciliation of issued vs delivered vouchers, activations, credit balances, and replacements; discrepancies resolved within 5 Business Days.

13. GOVERNING LAW & JURISDICTION
This Agreement shall be governed by the laws of India, including the Indian Contract Act, 1872. Disputes may be brought in the courts of Jaipur, Rajasthan (First Party's registered office), the courts having jurisdiction over the Second Party's declared office, New Delhi for matters of national importance or RBI-related issues, and arbitration as below. Each Party irrevocably submits to these courts on a non-exclusive basis. Any judgment or award obtained in one jurisdiction may be enforced in another forum in India.

14. DISPUTE RESOLUTION & ARBITRATION
14.1 Escalation: Order/delivery discrepancy — account managers, 3 Business Days; SLA breach — operations head, 5 Business Days; payment/refund — finance head, 7 Business Days; termination/material breach — executive director, 10 Business Days.
14.2 Mediation: If unresolved, either Party may initiate mediation; a neutral mediator shall be selected within 5 Business Days and mediation held within 14 days.
14.3 Arbitration: If mediation does not resolve the dispute within 30 days, arbitration under the Arbitration and Conciliation Act, 1996. Seat: New Delhi. Single arbitrator mutually agreed, failing which appointed by the Indian Arbitration Council. Governing law: India. Language: English. Each Party bears its own costs; arbitrator fees split equally. Award final and binding.
14.4 Interim Relief: Either Party may seek interim relief from any competent court.
14.5 No Waiver: Initiation of dispute resolution does not waive rights or extend deadlines unless expressly agreed.

15. MISCELLANEOUS
15.1 Amendment: Payswap may NOT unilaterally amend this Agreement. Material amendments require written consent from both Parties, clear intimation of change and effective date, and 15 days for Merchant to accept or reject. Minor housekeeping amendments may be made with notice.
15.2 Amendments for New Orders: Amendments apply only to new orders after both Parties consent, or existing standing orders if Merchant opts in. Existing orders under prior terms are not affected.
15.3 KYC/KYB: Merchant shall furnish KYC, KYB, board resolution or equivalent authority of the signatory, business purpose declaration, and beneficial ownership declaration where applicable. Supplier shall complete verification within 5 Business Days. Execution of this Agreement by Aadhaar eSign is permitted only after KYC, KYB, and bank verification have succeeded.
15.4 Entire Agreement: This Agreement, including Schedule A and Schedule B, constitutes the entire understanding and supersedes prior discussions.
15.5 Severability: Invalid provisions are severed; remaining provisions continue.
15.6 Waiver: No waiver is effective unless in writing signed by both Parties.
15.7 Notices: In writing via registered email with read receipt, registered post, or hand delivery.

Notices to First Party (Payswap): {first_email} (email), {first_office} (postal address)
Notices to Second Party (Merchant): {second_email} (email), {second_mobile} (mobile), {second_office} (postal address)

16. SCHEDULE A — SERVICE LEVEL AGREEMENT & DELIVERY TIMELINES
Service Component | Timeline | SLA Target | Service Credit on Breach
E-voucher delivery | Same-day (before 2 PM IST) | 100% | 2% for 1–3 days late; 5% for 4–7 days; full refund >7 days
E-voucher activation | Within 24 hours of delivery | 100% | Automatic replacement; refund after 2 failed attempts
Physical voucher dispatch | T+3 from cleared payment | 100% | Delay interest at 36% p.a. after T+5
Replacement of defective vouchers | Within 2 Business Days | 100% | Automatic refund if 2 replacements fail
Customer support response | Email within 4 hours (Business Days) | 100% | Escalation to senior management
Refund processing | Within 3 Business Days of approval | 100% | Interest at 36% p.a. if delayed
SLA breach reconciliation | Monthly by 10th of month | 100% | Dispute escalation to executive level

Notes: All timelines in Business Days unless specified. Day 0 = date of order acceptance or payment clearance (whichever is later). Service credits are cumulative for multiple breaches in a single order. Merchant may request refund in lieu of service credit if credit balance is insufficient.

17. SCHEDULE B — MERCHANT PARTICULARS (PREFILLED FROM VERIFIED KYC / KYB / BANK)
Merchant ID: {merchant_id}
Legal name: {second_legal_name}
Entity type: {entity_type}
Registered office / principal place of business: {second_office}
PAN: {pan}
GSTIN: {gstin}
CIN / LLPIN: {cin}
Authorized signatory: {second_signatory_name}
Designation: {second_signatory_designation}
Ownership declared: {ownership}
Email: {second_email}
Mobile: {second_mobile}
KYC verification: {kyc_status}
KYB verification: {kyb_status}
Bank verification: {bank_status}
Bank account holder: {bank_holder}
IFSC: {bank_ifsc}
Bank account (last 4 digits): {bank_last4}

The particulars above are drawn from the Merchant's verified onboarding record as of the Effective Date. Any material change shall be notified in writing and may require re-verification before further Orders are accepted.

SIGNATURES

For {first_legal_name} (First Party)
Authorized Signatory
Name: {first_signatory_name}
Designation: {first_signatory_designation}
Date: {effective_date}
Address: {first_office}
Email: {first_email}

For {second_legal_name} (Second Party)
Authorized Signatory
Name: {second_signatory_name}
Designation: {second_signatory_designation}
Date: {effective_date}
Address: {second_office}
Email: {second_email}
Merchant ID: {merchant_id}

The Second Party executes this Agreement by Aadhaar eSign after successful KYC verification. The First Party countersigns after the Merchant's eSign is complete.
"""
