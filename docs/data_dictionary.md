# Data dictionary

## Customer source

| Column | Type | Nullable | Business rule |
| --- | --- | --- | --- |
| customer_id | string | no | Stable primary key |
| email | string | no | Sensitive; tokenized |
| first_name | string | no | Sensitive; masked |
| last_name | string | no | Sensitive; masked |
| dob | date | no | Sensitive; reduced to year in analytics |
| phone | string | no | Sensitive; tokenized |
| ssn | string | no | Sensitive; tokenized |
| address | string | no | Sensitive; tokenized |
| city | string | no | Low-impact demographic field |
| state | string | no | Allowed state code |
| signup_date | date | no | Used for cohort analysis |
| customer_tier | string | no | Business segmentation |

## Order source

| Column | Type | Nullable | Business rule |
| --- | --- | --- | --- |
| order_id | string | no | Stable primary key |
| customer_id | string | no | Must exist in customer table |
| order_date | date | no | Used for recency analysis |
| order_total | number | no | Must be positive |
| channel | string | no | Sales channel classification |
| status | string | no | Payment/order state |

## Published analytics output

| Column | Type | Description |
| --- | --- | --- |
| customer_id | string | Stable identifier |
| customer_tier | string | Customer segment |
| state | string | Customer state |
| signup_year | int | Cohort year |
| order_count | int | Count of valid orders |
| total_spend | number | Summed order value |
| last_order_date | date | Most recent order |
| email_token | string | Tokenized email |
| phone_token | string | Tokenized phone |
| dob_year | int | Year-only birth-year representation |
