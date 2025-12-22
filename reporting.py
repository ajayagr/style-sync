from dataclasses import dataclass, field
from typing import List, Optional
import time
from datetime import datetime

@dataclass
class StepRecord:
    step_name: str
    status: str
    start_time: float
    end_time: float
    details: str
    error: Optional[str] = None
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

@dataclass
class RunContext:
    start_time: float = field(default_factory=time.time)
    input_type: str = "Unknown"
    input_path: str = ""
    output_type: str = "Unknown" 
    output_path: str = ""
    username: str = "Local User"
    
    files_found: int = 0
    expected_variants: int = 0
    missing_variants: List[str] = field(default_factory=list)
    orphan_variants: List[str] = field(default_factory=list)
    
    steps: List[StepRecord] = field(default_factory=list)
    
    def add_step(self, name: str, start_time: float, details: str, error: str = None):
        status = "Failed" if error else "Success"
        self.steps.append(StepRecord(
            step_name=name,
            status=status,
            start_time=start_time,
            end_time=time.time(),
            details=details,
            error=error
        ))

    def generate_markdown(self) -> str:
        duration = time.time() - self.start_time
        timestamp = datetime.fromtimestamp(self.start_time).strftime('%Y-%m-%d %H:%M:%S')
        
        md = [
            f"# StyleSync Run Report",
            f"**Date**: {timestamp}",
            f"**Duration**: {duration:.2f}s",
            f"**User**: {self.username}",
            "",
            "## Configuration",
            f"- **Input**: {self.input_type} (`{self.input_path}`)",
            f"- **Output**: {self.output_type} (`{self.output_path}`)",
            "",
            "## Statistics",
            f"| Metric | Count |",
            f"| :--- | :--- |",
            f"| Files Found | {self.files_found} |",
            f"| Expected Variants | {self.expected_variants} |",
            f"| Missing Variants | {len(self.missing_variants)} |",
            f"| Orphaned Variants | {len(self.orphan_variants)} |",
            "",
        ]
        
        if self.orphan_variants:
            md.append("### Orphaned Files (Cleaned)")
            for name in self.orphan_variants:
                md.append(f"- {name}")
            md.append("")

        md.append("## Execution Log")
        md.append("| Step | Status | Duration | Details |")
        md.append("| :--- | :--- | :--- | :--- |")
        
        for step in self.steps:
            duration_str = f"{step.duration:.2f}s"
            # Escape pipes in details to avoid breaking table
            clean_details = step.details.replace("|", "\\|").replace("\n", "<br>")
            md.append(f"| {step.step_name} | {step.status} | {duration_str} | {clean_details} |")
            
        return "\n".join(md)
