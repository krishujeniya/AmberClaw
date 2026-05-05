import os

def create_init_files(root_dir):
    for root, dirs, files in os.walk(root_dir):
        if "__init__.py" in files:
            file_path = os.path.join(root, "__init__.py")
            relative_path = os.path.relpath(root, root_dir)
            module_name = relative_path.replace(os.path.sep, ".")
            if module_name == ".":
                module_name = "amberclaw"
            else:
                module_name = f"amberclaw.{module_name}"
            
            content = f'"""\nAmberClaw {module_name} module.\n"""\n\nfrom pydantic import BaseModel, Field\n\n\nclass {module_name.split(".")[-1].capitalize()}ModuleConfig(BaseModel):\n    """Configuration for the {module_name} module."""\n    enabled: bool = Field(default=True, description="Whether the module is enabled")\n    version: str = Field(default="2026.0.1", description="Module version")\n\n\n__all__ = ["{module_name.split(".")[-1].capitalize()}ModuleConfig"]\n'
            
            with open(file_path, "w") as f:
                f.write(content)

if __name__ == "__main__":
    create_init_files("src/amberclaw")
