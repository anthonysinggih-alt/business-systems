# app.py
from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import datetime
from databases import (
    BaseItemSession, ComponentSession, ScheduleSession,
    BaseItem, Component, ComponentBOM, ProductionTask
)

app = Flask(__name__)
app.secret_key = "dev-key"


# =========================================================
# INDEX
# =========================================================
@app.route("/")
def index():
    return render_template("index.html")


# =========================================================
# ADMIN — Add Base Items and Components
# =========================================================
# app.py (unchanged except last render)
@app.route("/admin", methods=["GET", "POST"])
def admin():
    base_session = BaseItemSession()
    comp_session = ComponentSession()

    # --- Add Base Item ---
    if request.form.get("form_type") == "base":
        name = request.form["name"].strip()
        vendor = request.form.get("vendor", "").strip()
        unit_price = float(request.form.get("unit_price", 0))
        qty_in_stock = float(request.form.get("qty_in_stock", 0))
        if not name:
            flash("❌ Item name cannot be empty!", "danger")
        else:
            item = BaseItem(name=name, vendor=vendor, unit_price=unit_price, qty_in_stock=qty_in_stock)
            base_session.add(item)
            base_session.commit()
            flash(f"✅ Added base item: {name}", "success")
        return redirect(url_for("admin"))

    # --- Add Component + BOM ---
    if request.form.get("form_type") == "component":
        sku = request.form["sku"].strip()
        name = request.form["comp_name"].strip()
        lead_time = int(request.form.get("lead_time", 0))

        if not sku or not name:
            flash("❌ Component SKU and name are required.", "danger")
            return redirect(url_for("admin"))

        if comp_session.query(Component).filter_by(sku=sku).first():
            flash(f"⚠️ Component '{sku}' already exists!", "warning")
            return redirect(url_for("admin"))

        # ✅ qty_in_stock = 0 by default
        new_comp = Component(sku=sku, name=name, lead_time=lead_time, qty_in_stock=0.0)
        comp_session.add(new_comp)
        comp_session.commit()

        # Parse BOM lines
        child_skus = request.form.getlist("child_sku[]")
        qtys = request.form.getlist("qty_per[]")
        sources = request.form.getlist("source_type[]")

        added = 0
        for cs, q, src in zip(child_skus, qtys, sources):
            if not cs.strip():
                continue
            try:
                qty = float(q)
            except ValueError:
                qty = 0
            if qty <= 0:
                continue
            line = ComponentBOM(
                parent_sku=sku,
                child_sku=cs.strip(),
                qty_per=qty,
                source_type=src
            )
            comp_session.add(line)
            added += 1

        comp_session.commit()

        if added == 0:
            flash(f"⚠️ Component '{sku}' added (no valid BOM lines).", "warning")
        else:
            flash(f"✅ Component '{sku}' added with {added} BOM line(s).", "success")

        return redirect(url_for("admin"))

    # --- Load data ---
    base_items = base_session.query(BaseItem).all()
    components = comp_session.query(Component).all()

    # ✅ Build a dict of component -> child items
    bom_map = {}
    for comp in components:
        bom_lines = comp_session.query(ComponentBOM).filter_by(parent_sku=comp.sku).all()
        child_names = []
        for line in bom_lines:
            if line.source_type == "base":
                child = base_session.query(BaseItem).filter_by(name=line.child_sku).first()
                if child:
                    child_names.append(child.name)
                else:
                    child_names.append(line.child_sku)
            elif line.source_type == "component":
                child_comp = comp_session.query(Component).filter_by(sku=line.child_sku).first()
                if child_comp:
                    child_names.append(child_comp.name)
                else:
                    child_names.append(line.child_sku)
        bom_map[comp.sku] = ", ".join(child_names) if child_names else "-"

    return render_template(
        "admin.html",
        base_items=base_items,
        components=components,
        bom_map=bom_map
    )

# =========================================================
# PROCUREMENT
# =========================================================
@app.route("/procurement", methods=["GET", "POST"])
def procurement():
    session = BaseItemSession()
    items = session.query(BaseItem).all()

    if request.method == "POST":
        item_id = int(request.form["item_id"])
        qty = float(request.form.get("qty", 0))
        item = session.query(BaseItem).filter_by(id=item_id).first()

        if not item:
            flash("❌ Item not found!", "danger")
        else:
            item.qty_in_stock += qty
            session.commit()
            flash(f"📦 Purchased {qty} units of '{item.name}'. New stock: {item.qty_in_stock}", "success")

        return redirect(url_for("procurement"))

    return render_template("procurement.html", items=items)


# =========================================================
# SCHEDULING
# =========================================================

@app.route("/schedule", methods=["GET", "POST"])
def schedule():
    comp_session = ComponentSession()
    sched_session = ScheduleSession()

    # --- Add new task ---
    if request.method == "POST" and request.form.get("form_type") == "add_task":
        sku = request.form.get("component_sku")
        qty = int(request.form.get("qty", 1))

        if not sku:
            flash("❌ Please select a component.", "danger")
            return redirect(url_for("schedule"))

        new_task = ProductionTask(component_sku=sku, status="pending", quantity=qty)
        sched_session.add(new_task)
        sched_session.commit()

        flash(f"🧾 Scheduled production of {qty} unit(s) of '{sku}'", "success")
        return redirect(url_for("schedule"))

    # --- Update task status or delete ---
    if request.method == "POST" and request.form.get("form_type") == "update_task":
        task_id = int(request.form["task_id"])
        action = request.form["action"]
        task = sched_session.query(ProductionTask).filter_by(id=task_id).first()

        if not task:
            flash("❌ Task not found.", "danger")
            return redirect(url_for("schedule"))

        if action == "complete":
            task.status = "completed"
            comp = comp_session.query(Component).filter_by(sku=task.component_sku).first()
            if comp:
                comp.qty_in_stock += task.quantity
                comp_session.commit()
            flash(f"✅ Completed {task.quantity} unit(s) of '{task.component_sku}', stock +{task.quantity}", "success")
        elif action == "cancel":
            # ✅ Delete the task entirely
            sched_session.delete(task)
            flash(f"🗑 Deleted scheduled task for '{task.component_sku}'", "warning")

        sched_session.commit()
        return redirect(url_for("schedule"))

    # --- Load components & tasks ---
    components = comp_session.query(Component).all()
    tasks = sched_session.query(ProductionTask).order_by(ProductionTask.id.desc()).all()

    # --- Build a quick lookup map for component info ---
    comp_map = {c.sku: {"name": c.name, "lead_time": c.lead_time} for c in components}

    # --- Compute ETA, overdue status, and name ---
    now = datetime.now()
    enriched_tasks = []

    for t in tasks:
        comp_info = comp_map.get(t.component_sku, {"name": "(Unknown)", "lead_time": 0})
        eta_str = t.estimated_completion
        eta = None
        try:
            eta = datetime.strptime(eta_str, "%Y-%m-%d %H:%M") if eta_str != "-" else None
        except:
            pass

        is_overdue = t.status == "pending" and eta and eta < now

        enriched_tasks.append({
            "id": t.id,
            "component_sku": t.component_sku,
            "component_name": comp_info["name"],
            "lead_time": comp_info["lead_time"],
            "status": t.status,
            "created_at": t.created_at,
            "estimated_completion": eta_str,
            "quantity": getattr(t, "quantity", 1),
            "is_overdue": is_overdue
        })

    return render_template("schedule.html", components=components, tasks=enriched_tasks)


# =========================================================
# RUN
# =========================================================
if __name__ == "__main__":
    app.run(debug=True)

