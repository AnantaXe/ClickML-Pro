"""
ClickML-Pro Gradio Dashboard — visual interface for every module.

Launch:  clickml ui
         python -m clickml_pro.ui.dashboard
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _safe_import_gradio():
    try:
        import gradio as gr
        return gr
    except ImportError:
        raise ImportError(
            "Gradio is required for the UI. Install with:\n"
            "  pip install 'clickml-pro[ui]'"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Tab builders — each returns a gr.Tab context
# ═══════════════════════════════════════════════════════════════════════════


def _build_training_tab(gr):
    """Training configuration & launch."""

    with gr.Tab("🏋️ Training") as tab:
        gr.Markdown("## Model Training\nConfigure and launch training jobs.")

        with gr.Row():
            with gr.Column(scale=2):
                base_model = gr.Textbox(
                    label="Base Model",
                    value="meta-llama/Llama-3.1-8B",
                    placeholder="HuggingFace model ID or local path",
                )
                mode = gr.Dropdown(
                    label="Training Mode",
                    choices=["pretrain", "finetune", "lora", "sft", "rlhf", "diffusion"],
                    value="lora",
                )
                dataset = gr.Textbox(
                    label="Dataset",
                    placeholder="HuggingFace dataset or local path",
                )

            with gr.Column(scale=1):
                epochs = gr.Slider(1, 100, value=3, step=1, label="Epochs")
                batch_size = gr.Slider(1, 128, value=4, step=1, label="Batch Size")
                lr = gr.Number(value=2e-5, label="Learning Rate")
                output_dir = gr.Textbox(label="Output Directory", value="./output")

        with gr.Accordion("LoRA / PEFT Settings", open=False):
            with gr.Row():
                lora_r = gr.Slider(4, 256, value=16, step=4, label="LoRA Rank (r)")
                lora_alpha = gr.Slider(8, 512, value=32, step=8, label="LoRA Alpha")
                lora_dropout = gr.Slider(0, 0.5, value=0.05, step=0.01, label="Dropout")
            target_modules = gr.Textbox(
                label="Target Modules (comma-separated)",
                value="q_proj, v_proj",
            )

        with gr.Accordion("Distributed Training", open=False):
            with gr.Row():
                strategy = gr.Dropdown(
                    ["none", "ddp", "fsdp", "deepspeed_zero1", "deepspeed_zero2", "deepspeed_zero3"],
                    value="none",
                    label="Strategy",
                )
                num_gpus = gr.Slider(1, 8, value=1, step=1, label="GPUs")

        with gr.Row():
            estimate_btn = gr.Button("💰 Estimate Cost", variant="secondary")
            train_btn = gr.Button("🚀 Start Training", variant="primary")

        cost_output = gr.JSON(label="Cost Estimate")
        train_output = gr.JSON(label="Training Result")

        def _estimate_cost(base_model, mode, epochs, batch_size):
            from clickml_pro.governance.cost import CostEstimator
            estimator = CostEstimator()
            est = estimator.estimate({
                "type": "training",
                "base_model": base_model,
                "mode": mode,
                "training": {"epochs": epochs, "batch_size": batch_size},
            })
            return est.model_dump()

        def _run_training(base_model, mode, dataset, epochs, batch_size, lr, output_dir,
                          lora_r, lora_alpha, lora_dropout, target_modules, strategy, num_gpus):
            from clickml_pro.training.manager import TrainingManager
            config: dict[str, Any] = {
                "base_model": base_model,
                "mode": mode,
                "dataset": dataset,
                "training": {
                    "epochs": int(epochs),
                    "batch_size": int(batch_size),
                    "learning_rate": float(lr),
                },
                "output_dir": output_dir,
            }
            if mode in ("lora", "peft", "sft"):
                config["lora"] = {
                    "r": int(lora_r),
                    "alpha": int(lora_alpha),
                    "dropout": float(lora_dropout),
                    "target_modules": [m.strip() for m in target_modules.split(",")],
                }
            if strategy != "none":
                config["distributed"] = {"strategy": strategy, "num_gpus": int(num_gpus)}
            try:
                manager = TrainingManager()
                result = manager.run(config)
                return result
            except Exception as exc:
                return {"error": str(exc)}

        estimate_btn.click(
            _estimate_cost,
            inputs=[base_model, mode, epochs, batch_size],
            outputs=cost_output,
        )
        train_btn.click(
            _run_training,
            inputs=[base_model, mode, dataset, epochs, batch_size, lr, output_dir,
                    lora_r, lora_alpha, lora_dropout, target_modules, strategy, num_gpus],
            outputs=train_output,
        )

    return tab


def _build_quantization_tab(gr):
    """Quantization pipeline UI."""

    with gr.Tab("⚡ Quantization") as tab:
        gr.Markdown("## Model Quantization\nCompress models for efficient deployment.")

        with gr.Row():
            model_path = gr.Textbox(label="Model Path", placeholder="./output or HuggingFace ID")
            output_dir = gr.Textbox(label="Output Directory", value="./quantized")

        methods = gr.CheckboxGroup(
            ["int8", "int4", "awq", "gptq", "gguf", "onnx"],
            label="Quantization Methods",
            value=["int8"],
        )

        run_btn = gr.Button("⚡ Quantize", variant="primary")
        result = gr.JSON(label="Quantization Results")

        def _run_quant(model_path, output_dir, methods):
            from clickml_pro.quantization.pipeline import QuantizationPipeline
            pipeline = QuantizationPipeline()
            try:
                return pipeline.run(model_path=model_path, output_dir=output_dir, methods=methods)
            except Exception as exc:
                return {"error": str(exc)}

        run_btn.click(_run_quant, inputs=[model_path, output_dir, methods], outputs=result)

    return tab


def _build_registry_tab(gr):
    """Model registry browser."""

    with gr.Tab("📦 Registry") as tab:
        gr.Markdown("## Model Registry\nBrowse, register, and promote models.")

        with gr.Row():
            refresh_btn = gr.Button("🔄 Refresh", variant="secondary")
            search_box = gr.Textbox(label="Search", placeholder="model name...")

        models_table = gr.JSON(label="Registered Models")

        with gr.Accordion("Register New Model", open=False):
            with gr.Row():
                reg_name = gr.Textbox(label="Model Name")
                reg_desc = gr.Textbox(label="Description")
                reg_owner = gr.Textbox(label="Owner")
            with gr.Row():
                reg_base = gr.Textbox(label="Base Model")
                reg_tags = gr.Textbox(label="Tags (comma-separated)")
            register_btn = gr.Button("📝 Register", variant="primary")
            reg_result = gr.JSON(label="Registration Result")

        def _list_models(query):
            from clickml_pro.registry.model_registry import ModelRegistry
            registry = ModelRegistry()
            if query:
                models = registry.search(query)
            else:
                models = registry.list_models()
            return [m.model_dump() for m in models]

        def _register_model(name, desc, owner, base, tags_str):
            from clickml_pro.registry.model_registry import ModelRegistry, RegisteredModel, ModelLineage
            registry = ModelRegistry()
            tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []
            model = RegisteredModel(
                name=name,
                description=desc,
                owner=owner,
                lineage=ModelLineage(base_model=base),
                tags=tags,
            )
            entry = registry.register(model)
            return entry.model_dump()

        refresh_btn.click(_list_models, inputs=[search_box], outputs=models_table)
        search_box.submit(_list_models, inputs=[search_box], outputs=models_table)
        register_btn.click(
            _register_model,
            inputs=[reg_name, reg_desc, reg_owner, reg_base, reg_tags],
            outputs=reg_result,
        )

    return tab


def _build_data_tab(gr):
    """Data engineering tools."""

    with gr.Tab("🗄️ Data") as tab:
        gr.Markdown("## Data Engineering\nSchema management, lineage, and observability.")

        with gr.Tabs():
            with gr.Tab("Schema"):
                with gr.Row():
                    schema_dataset = gr.Textbox(label="Dataset Name", placeholder="users")
                    schema_refresh = gr.Button("🔄 Load Schema")
                schema_output = gr.JSON(label="Schema")

                def _load_schema(dataset):
                    from clickml_pro.data.schema.manager import SchemaManager
                    mgr = SchemaManager()
                    s = mgr.get_latest(dataset)
                    return s.model_dump() if s else {"message": f"No schema found for '{dataset}'"}

                schema_refresh.click(_load_schema, inputs=[schema_dataset], outputs=schema_output)

            with gr.Tab("Lineage"):
                gr.Markdown("Query upstream/downstream data lineage.")
                with gr.Row():
                    node_id = gr.Textbox(label="Node ID")
                    direction = gr.Radio(["upstream", "downstream"], value="downstream", label="Direction")
                    lineage_btn = gr.Button("🔍 Query")
                lineage_output = gr.JSON(label="Lineage")

                def _query_lineage(node_id, direction):
                    from clickml_pro.data.lineage.graph import LineageGraph
                    graph = LineageGraph()
                    if direction == "upstream":
                        return {"node": node_id, "upstream": graph.upstream(node_id)}
                    return {"node": node_id, "downstream": graph.downstream(node_id)}

                lineage_btn.click(_query_lineage, inputs=[node_id, direction], outputs=lineage_output)

    return tab


def _build_governance_tab(gr):
    """Governance dashboard — budgets, quotas, policies."""

    with gr.Tab("🛡️ Governance") as tab:
        gr.Markdown("## Governance & Cost Management")

        with gr.Tabs():
            # ── Cost estimator ──
            with gr.Tab("Cost Estimator"):
                with gr.Row():
                    est_model = gr.Textbox(label="Model", value="llama-7b")
                    est_mode = gr.Dropdown(
                        ["pretrain", "finetune", "lora", "sft"],
                        value="lora",
                        label="Mode",
                    )
                with gr.Row():
                    est_epochs = gr.Slider(1, 50, value=3, step=1, label="Epochs")
                    est_batch = gr.Slider(1, 64, value=4, step=1, label="Batch Size")
                est_btn = gr.Button("💰 Estimate")
                est_output = gr.JSON(label="Estimate")

                def _estimate(model, mode, epochs, batch):
                    from clickml_pro.governance.cost import CostEstimator
                    estimator = CostEstimator()
                    return estimator.estimate({
                        "type": "training",
                        "base_model": model,
                        "mode": mode,
                        "training": {"epochs": epochs, "batch_size": batch},
                    }).model_dump()

                est_btn.click(_estimate, inputs=[est_model, est_mode, est_epochs, est_batch], outputs=est_output)

            # ── Budgets ──
            with gr.Tab("Budgets"):
                with gr.Row():
                    bud_entity = gr.Textbox(label="Entity ID", placeholder="org-1")
                    bud_refresh = gr.Button("🔄 View Budget")
                bud_output = gr.JSON(label="Budget Summary")

                with gr.Accordion("Set Budget", open=False):
                    with gr.Row():
                        bud_set_entity = gr.Textbox(label="Entity ID")
                        bud_set_limit = gr.Number(value=500, label="Limit (USD)")
                    bud_set_btn = gr.Button("💵 Set Budget")
                    bud_set_result = gr.JSON(label="Result")

                def _view_budget(entity_id):
                    from clickml_pro.governance.budget import BudgetManager
                    return BudgetManager().get_summary(entity_id)

                def _set_budget(entity_id, limit):
                    from clickml_pro.governance.budget import BudgetManager
                    record = BudgetManager().set_budget(entity_id, limit_usd=float(limit))
                    return record.model_dump()

                bud_refresh.click(_view_budget, inputs=[bud_entity], outputs=bud_output)
                bud_set_btn.click(_set_budget, inputs=[bud_set_entity, bud_set_limit], outputs=bud_set_result)

            # ── Quotas ──
            with gr.Tab("Quotas"):
                with gr.Row():
                    q_org = gr.Textbox(label="Org ID")
                    q_refresh = gr.Button("🔄 Check Quota")
                q_output = gr.JSON(label="Quota Status")

                def _check_quota(org_id):
                    from clickml_pro.governance.quotas import QuotaManager
                    mgr = QuotaManager()
                    entry = mgr.get_quota(org_id)
                    if entry:
                        return entry.model_dump()
                    return {"message": f"No quota found for '{org_id}'"}

                q_refresh.click(_check_quota, inputs=[q_org], outputs=q_output)

            # ── Policies ──
            with gr.Tab("Policies"):
                pol_refresh = gr.Button("🔄 List Policies")
                pol_output = gr.JSON(label="Policies")

                def _list_policies():
                    from clickml_pro.governance.policies import PolicyEngine
                    return [p.model_dump() for p in PolicyEngine().list_policies()]

                pol_refresh.click(_list_policies, outputs=pol_output)

    return tab


def _build_notebook_tab(gr):
    """Notebook generator & exporter."""

    with gr.Tab("📓 Notebook") as tab:
        gr.Markdown("## Notebook Generator\nAuto-generate and export Jupyter notebooks.")

        with gr.Tabs():
            with gr.Tab("Generate"):
                template = gr.Dropdown(
                    ["training", "pipeline"],
                    value="training",
                    label="Template",
                )
                config_json = gr.Code(
                    label="Config (JSON)",
                    language="json",
                    value='{\n  "base_model": "meta-llama/Llama-3.1-8B",\n  "mode": "lora"\n}',
                )
                gen_btn = gr.Button("📓 Generate Notebook", variant="primary")
                nb_output = gr.Code(label="Generated Notebook (JSON)", language="json")
                save_path = gr.Textbox(label="Save As", value="./generated_notebook.ipynb")
                save_btn = gr.Button("💾 Save to Disk")
                save_result = gr.Textbox(label="Save Result")

                def _generate(template, config_str):
                    from clickml_pro.notebook.editor import NotebookEditor
                    config = json.loads(config_str)
                    if template == "training":
                        nb = NotebookEditor.from_training_config(config)
                    else:
                        nb = NotebookEditor.from_pipeline_config(config)
                    return nb.to_json(indent=2)

                def _save_nb(nb_json, path):
                    try:
                        Path(path).parent.mkdir(parents=True, exist_ok=True)
                        Path(path).write_text(nb_json, encoding="utf-8")
                        return f"✅ Saved to {path}"
                    except Exception as exc:
                        return f"❌ {exc}"

                gen_btn.click(_generate, inputs=[template, config_json], outputs=nb_output)
                save_btn.click(_save_nb, inputs=[nb_output, save_path], outputs=save_result)

            with gr.Tab("Export"):
                upload = gr.File(label="Upload .ipynb", file_types=[".ipynb"])
                export_fmt = gr.Dropdown(["python", "html", "markdown"], value="python", label="Format")
                export_btn = gr.Button("📤 Export")
                export_result = gr.File(label="Exported File")

                def _export(file, fmt):
                    if file is None:
                        return None
                    from clickml_pro.notebook.exporter import NotebookExporter
                    exporter = NotebookExporter()
                    out = exporter.export(file.name, fmt=fmt)
                    return str(out)

                export_btn.click(_export, inputs=[upload, export_fmt], outputs=export_result)

    return tab


# ═══════════════════════════════════════════════════════════════════════════
# Main dashboard
# ═══════════════════════════════════════════════════════════════════════════


def create_dashboard(
    server_name: str = "0.0.0.0",
    server_port: int = 7860,
    share: bool = False,
    **kwargs,
):
    """Build and return (or launch) the Gradio Blocks dashboard."""
    gr = _safe_import_gradio()

    with gr.Blocks(
        title="ClickML Pro",
        theme=gr.themes.Soft(),
        css="""
        .gradio-container { max-width: 1400px !important; }
        footer { display: none !important; }
        """,
    ) as demo:
        gr.Markdown(
            "# 🧠 ClickML Pro\n"
            "**Enterprise MLOps & Data Engineering Dashboard**\n\n"
            "Train · Quantize · Register · Govern · Export"
        )

        _build_training_tab(gr)
        _build_quantization_tab(gr)
        _build_registry_tab(gr)
        _build_data_tab(gr)
        _build_governance_tab(gr)
        _build_notebook_tab(gr)

    return demo


def launch(**kwargs):
    """Create and launch the dashboard."""
    demo = create_dashboard(**kwargs)
    demo.launch(
        server_name=kwargs.get("server_name", "0.0.0.0"),
        server_port=kwargs.get("server_port", 7860),
        share=kwargs.get("share", False),
    )


if __name__ == "__main__":
    launch()
