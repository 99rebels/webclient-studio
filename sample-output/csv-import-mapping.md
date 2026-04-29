**CSV Import — Column Mapping**

I've read your file `contacts-april-2026.csv`. Here are the headers and a sample of the data:

| Biz Name | Website | Contact | Email | Priority | Source |
|---|---|---|---|---|---|
| Summit Dental Care | summitdentalcare.ie | Dr. A. Murphy | amurphy@summit.ie | 8 | Networking |
| Clearview Physio | clearviewphysio.ie | Jane Walsh | jane@clearview.ie | 7 | Google |
| The Green Room Café | N/A | Tom Ryan | tom@greenroom.ie | 5 | Referral |
| Galway Autism Support | galwayautism.ie | S. O'Brien | sarah@galwayautism.ie | 7 | Website |
| West Coast Plumbing | wcplumbing.ie | M. Kelly | mark@wcplumbing.ie | NULL | Cold email |

---

**Proposed mapping:**

| Your column | Our field | Notes |
|---|---|---|
| Biz Name | `company` | ✅ |
| Website | `website` | ✅ (will add https:// where missing) |
| Contact | `contact_name` | ✅ |
| Email | `contact_email` | ✅ |
| Priority | `lead_score` | ✅ (validated: 1–10) |
| Source | — | **skip** (not in our schema) |

---

**Preview (5 rows):**

| Company | Website | Score | Status |
|---|---|---|---|
| Summit Dental Care | summitdentalcare.ie | 8 | lead |
| Clearview Physio | clearviewphysio.ie | 7 | lead |
| The Green Room Café | *(no website)* | 5 | lead |
| Galway Autism Support | galwayautism.ie | 7 | lead |
| West Coast Plumbing | wcplumbing.ie | NULL | lead |

⚠️ 1 row has no website — will import with NULL
⚠️ 1 row has NULL score — will import with NULL

**Summary:** 5 rows to import · 0 duplicates · 2 with missing data
Defaults: status = lead, confidence = LOW, tag = imported

Does this mapping look right? Say "go" to import.
