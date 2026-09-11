import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import type { Action, ActionPatch } from "../types";

export function EditTask({
  item,
  revision,
  onClose,
  onSave,
}: {
  item: Action;
  revision: number;
  onClose: () => void;
  onSave: (patch: ActionPatch) => Promise<void>;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [task, setTask] = useState(item.task);
  const [assignee, setAssignee] = useState(item.assignee ?? "");
  const [due, setDue] = useState(item.due.date ?? "");
  const [priority, setPriority] = useState<Action["priority"]>(item.priority);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    const element = dialog.current;
    element?.showModal();
    return () => element?.close();
  }, []);
  return (
    <dialog
      ref={dialog}
      className="edit-dialog"
      aria-labelledby="edit-action-title"
      onCancel={onClose}
    >
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setSaving(true);
          setError("");
          try {
            await onSave({
              revision,
              task: task.trim(),
              assignee: assignee.trim() || null,
              due_date: due || null,
              priority,
            });
            onClose();
          } catch (err) {
            setError((err as Error).message);
          } finally {
            setSaving(false);
          }
        }}
      >
        <div className="dialog-heading">
          <h2 id="edit-action-title">Edit action item</h2>
          <button
            type="button"
            className="icon-button"
            aria-label="Close editor"
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </div>
        <p className="muted">
          Changes are saved as a new report revision and marked as edited.
        </p>
        <label>
          Task
          <textarea
            required
            maxLength={2000}
            value={task}
            onChange={(e) => setTask(e.target.value)}
          />
        </label>
        <label>
          Owner
          <input
            value={assignee}
            maxLength={200}
            onChange={(e) => setAssignee(e.target.value)}
            placeholder="Unassigned"
          />
        </label>
        <div className="upload-options">
          <label>
            Due date
            <input
              type="date"
              value={due}
              onChange={(e) => setDue(e.target.value)}
            />
          </label>
          <label>
            Priority
            <select
              value={priority}
              onChange={(e) =>
                setPriority(e.target.value as Action["priority"])
              }
            >
              <option value="unspecified">Not specified</option>
              <option value="low">Low</option>
              <option value="normal">Normal</option>
              <option value="high">High</option>
            </select>
          </label>
        </div>
        {error && (
          <p role="alert" className="form-error">
            {error}
          </p>
        )}
        <div className="dialog-actions">
          <button type="button" className="secondary-button" onClick={onClose}>
            Cancel
          </button>
          <button className="primary-button" disabled={saving || !task.trim()}>
            {saving ? "Saving…" : "Save changes"}
          </button>
        </div>
      </form>
    </dialog>
  );
}
