import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
  Plus,
  Trash2,
  Save,
  FolderOpen,
  RotateCcw,
  Share2,
  AlertCircle,
} from "lucide-react";

/**
 * Generic Workflow Builder — the primary demonstration mode.
 *
 * Fully configurable: editable Workflow Name, dynamic custom fields
 * (label/value), dynamic checks, a Simulate Failure toggle, and browser-only
 * template persistence + sharing. It only edits the `config` object; proof
 * generation lives in TransactionFlow and uses the unchanged proof engine.
 */
export default function WorkflowBuilder({
  config,
  onChange,
  validation,
  onSave,
  onLoad,
  onReset,
  onShare,
}) {
  const setWorkflowName = (v) => onChange({ ...config, workflowName: v });

  const addField = () =>
    onChange({ ...config, fields: [...config.fields, { label: "", value: "" }] });
  const removeField = (i) =>
    onChange({ ...config, fields: config.fields.filter((_, idx) => idx !== i) });
  const updateField = (i, key, v) =>
    onChange({
      ...config,
      fields: config.fields.map((f, idx) =>
        idx === i ? { ...f, [key]: v } : f
      ),
    });

  const addCheck = () =>
    onChange({ ...config, checks: [...config.checks, { name: "" }] });
  const removeCheck = (i) =>
    onChange({ ...config, checks: config.checks.filter((_, idx) => idx !== i) });
  const updateCheck = (i, v) =>
    onChange({
      ...config,
      checks: config.checks.map((c, idx) => (idx === i ? { name: v } : c)),
    });

  return (
    <div className="space-y-7" data-testid="workflow-builder">
      {/* Workflow Name */}
      <div className="space-y-1.5">
        <Label className="text-xs font-medium text-gray-600 uppercase tracking-wide">
          Workflow Name
        </Label>
        <Input
          value={config.workflowName}
          onChange={(e) => setWorkflowName(e.target.value)}
          placeholder="e.g. Release, Change, Ticket, Employee, Invoice, Claim, AI Decision"
          className="bg-white border-gray-200 text-gray-900 h-11 text-base focus-visible:ring-2 focus-visible:ring-blue-500/30 focus-visible:border-blue-400"
          data-testid="builder-workflow-name"
        />
        <p className="text-xs text-gray-400">
          Name the thing you're proving — fully editable, not hardcoded.
        </p>
      </div>

      {/* Custom Fields */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.12em] text-gray-500">
              Custom Fields
            </div>
            <p className="text-xs text-gray-400 mt-0.5">
              Label / value pairs. Empty fields are excluded from the proof.
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={addField}
            className="border-gray-200 text-gray-700 hover:bg-gray-50"
            data-testid="builder-add-field"
          >
            <Plus className="w-3.5 h-3.5 mr-1.5" />
            Add Field
          </Button>
        </div>

        <div className="space-y-2.5" data-testid="builder-fields">
          {config.fields.length === 0 && (
            <p
              className="text-sm text-gray-400 italic px-1"
              data-testid="builder-fields-empty"
            >
              No fields yet — add at least one.
            </p>
          )}
          {config.fields.map((f, i) => (
            <div
              key={i}
              className="grid grid-cols-[1fr_1fr_auto] gap-2 items-center"
              data-testid={`builder-field-row-${i}`}
            >
              <Input
                value={f.label}
                onChange={(e) => updateField(i, "label", e.target.value)}
                placeholder="Field Label"
                className="bg-white border-gray-200 text-gray-900 h-10 text-sm focus-visible:ring-2 focus-visible:ring-blue-500/30 focus-visible:border-blue-400"
                data-testid={`builder-field-label-${i}`}
              />
              <Input
                value={f.value}
                onChange={(e) => updateField(i, "value", e.target.value)}
                placeholder="Field Value"
                className="bg-white border-gray-200 text-gray-900 h-10 text-sm font-mono focus-visible:ring-2 focus-visible:ring-blue-500/30 focus-visible:border-blue-400"
                data-testid={`builder-field-value-${i}`}
              />
              <button
                type="button"
                onClick={() => removeField(i)}
                className="w-10 h-10 flex items-center justify-center rounded-md text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                aria-label="Remove field"
                data-testid={`builder-remove-field-${i}`}
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Workflow Checks */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.12em] text-gray-500">
              Workflow Checks
            </div>
            <p className="text-xs text-gray-400 mt-0.5">
              Each check is recorded in the proof. Use Simulate Failure to fail
              them all.
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={addCheck}
            className="border-gray-200 text-gray-700 hover:bg-gray-50"
            data-testid="builder-add-check"
          >
            <Plus className="w-3.5 h-3.5 mr-1.5" />
            Add Check
          </Button>
        </div>

        <div className="space-y-2.5" data-testid="builder-checks">
          {config.checks.length === 0 && (
            <p
              className="text-sm text-gray-400 italic px-1"
              data-testid="builder-checks-empty"
            >
              No checks yet — add at least one.
            </p>
          )}
          {config.checks.map((c, i) => (
            <div
              key={i}
              className="grid grid-cols-[1fr_auto] gap-2 items-center"
              data-testid={`builder-check-row-${i}`}
            >
              <Input
                value={c.name}
                onChange={(e) => updateCheck(i, e.target.value)}
                placeholder="Check name (e.g. Manager Approval)"
                className="bg-white border-gray-200 text-gray-900 h-10 text-sm focus-visible:ring-2 focus-visible:ring-blue-500/30 focus-visible:border-blue-400"
                data-testid={`builder-check-name-${i}`}
              />
              <button
                type="button"
                onClick={() => removeCheck(i)}
                className="w-10 h-10 flex items-center justify-center rounded-md text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                aria-label="Remove check"
                data-testid={`builder-remove-check-${i}`}
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>

        {/* Simulate Failure (demonstration only) */}
        <div className="mt-4 flex items-center justify-between rounded-lg border border-gray-200 bg-gray-50 px-4 py-3">
          <div className="flex items-center gap-2">
            <Label
              htmlFor="builder-simulate-failure"
              className="text-sm text-gray-700"
            >
              Simulate Failure
            </Label>
            <span className="text-xs text-gray-400">
              (sets every check to failed — demo only)
            </span>
          </div>
          <Switch
            id="builder-simulate-failure"
            checked={config.simulateFailure}
            onCheckedChange={(v) => onChange({ ...config, simulateFailure: v })}
            data-testid="builder-simulate-failure"
          />
        </div>
      </div>

      {/* Validation */}
      {validation && !validation.valid && (
        <div
          className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3"
          data-testid="builder-validation"
        >
          <div className="flex items-center gap-2 text-sm font-medium text-amber-800">
            <AlertCircle className="w-4 h-4" />
            Resolve before generating a proof:
          </div>
          <ul className="mt-1.5 ml-6 list-disc text-sm text-amber-700 space-y-0.5">
            {validation.errors.map((e, i) => (
              <li key={i} data-testid={`builder-validation-error-${i}`}>
                {e}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Template controls — browser-only persistence */}
      <div className="flex flex-wrap gap-2 pt-4 border-t border-gray-100">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onSave}
          className="border-gray-200 text-gray-700 hover:bg-gray-50"
          data-testid="builder-save-template"
        >
          <Save className="w-3.5 h-3.5 mr-1.5" />
          Save Template
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onLoad}
          className="border-gray-200 text-gray-700 hover:bg-gray-50"
          data-testid="builder-load-template"
        >
          <FolderOpen className="w-3.5 h-3.5 mr-1.5" />
          Load Last Template
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onReset}
          className="border-gray-200 text-gray-700 hover:bg-gray-50"
          data-testid="builder-reset-template"
        >
          <RotateCcw className="w-3.5 h-3.5 mr-1.5" />
          Reset Template
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onShare}
          className="border-gray-200 text-gray-700 hover:bg-gray-50"
          data-testid="builder-share-template"
        >
          <Share2 className="w-3.5 h-3.5 mr-1.5" />
          Share Template
        </Button>
      </div>
    </div>
  );
}
