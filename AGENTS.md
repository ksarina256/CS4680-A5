# Launchpad Studio — a one-person company run by AI agents

If the environment variable `COMPANY_ROLE` is set (or your boot prompt names a role), you are an **agent
employee**: read `agents/_protocol.md` and your role card in `agents/<role>.md`, then follow them exactly.
Collaborate only through `python3 company.py` and files under `workspace/`.

If `COMPANY_ROLE` is not set, you are helping the human develop this repository: see `README.md`. Run the tests with
`python3 -m unittest discover -s tests -v`.
