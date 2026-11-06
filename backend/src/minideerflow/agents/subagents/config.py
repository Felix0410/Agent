"""固定两个只读角色；不支持动态角色、网络检索或再次委派。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SubAgentSpec:
    name: str
    system_prompt: str
    allowed_tools: tuple[str, ...]
    max_steps: int = 14
    timeout: float = 35


SPECS = {
    "general": SubAgentSpec(
        "general",
        "Complete only the delegated goal using provided information, calculation or current conversation files. Read files with list_files/read_text when needed. No web access, delegation, or file writing. Return concise findings and missing information. Never claim a failed tool succeeded.",
        ("calculate", "list_files", "read_text"),
    ),
    "research": SubAgentSpec(
        "research",
        "Analyze only provided information and current conversation files. No internet access or online research. Use list_files/read_text for actual evidence. Return concise findings, evidence file IDs and missing information. No writing or delegation. Never claim a failed tool succeeded.",
        ("list_files", "read_text"),
    ),
}
