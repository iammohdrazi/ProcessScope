"""ProcessScope — Process hooking and inspection."""

from processscope.process.attacher import ProcessAttacher
from processscope.process.metadata import ProcessMetadata, collect_metadata
from processscope.process.binary import BinaryInfo, analyze_binary
from processscope.process.tree import ProcessTree, build_process_tree

__all__ = [
    "ProcessAttacher",
    "ProcessMetadata", "collect_metadata",
    "BinaryInfo", "analyze_binary",
    "ProcessTree", "build_process_tree",
]
