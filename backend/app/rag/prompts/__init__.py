"""Load UTF-8 policies and build role-aware LangChain prompts. Re-evaluate after prompt edits.

Phụ trách: TV3 · [S3] Generation
"""

from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


def prompt(name: str) -> str:
    return (Path(__file__).parent / f"{name}.md").read_text(encoding="utf-8")


def generation_prompt() -> ChatPromptTemplate:
    # Values containing JSON/braces are inserted once, never re-parsed as templates.
    return ChatPromptTemplate.from_messages(
        [
            ("system", "{persona}\nLanguage: {lang}. Spoilers allowed: {spoilers}.\n{policy}"),
            MessagesPlaceholder("history"),
            ("human", "{payload}"),
        ]
    )


def rewrite_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", "{policy}"),
            MessagesPlaceholder("history"),
            ("human", "{question}"),
        ]
    )
