# Publication Safety Review

This directory is a clean public scaffold for the hackathon submission.

## Included

- Strands Agents SDK orchestration code
- Explainable QC policy
- Synthetic event examples
- Automated policy tests
- Architecture and setup documentation
- MIT License

## Deliberately excluded

- Real patient or family images
- Names, addresses, birthdays, or care identifiers
- Actual care logs
- Local camera device identifiers
- Wi-Fi, SSH, API, and AWS credentials
- `.env` files and local configuration
- Runtime JSONL output
- Raw toilet images
- Private-repository history

## Before every public update

1. Confirm examples remain synthetic.
2. Search for credentials, email addresses, absolute home-directory paths, and device identifiers.
3. Run the tests.
4. Verify `.gitignore` excludes local/runtime content.
5. Review the diff before publishing.

## Safety boundary

This project supports observation, recordkeeping, and handoff communication. It does not diagnose constipation, diarrhea, gastrointestinal disease, or any other condition. A missed observation is not proof that no bowel movement occurred.
