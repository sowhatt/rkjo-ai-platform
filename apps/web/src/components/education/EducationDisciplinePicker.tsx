"use client";

export type EducationDiscipline =
  | "mathematics"
  | "medicine"
  | "biology"
  | "general";

const OPTIONS: ReadonlyArray<{
  value: EducationDiscipline;
  label: string;
  description: string;
}> = [
  { value: "mathematics", label: "Mathématiques", description: "Calculs, exercices et raisonnement" },
  { value: "medicine", label: "Médecine", description: "Anatomie et physiologie académiques" },
  { value: "biology", label: "Biologie", description: "Cellules, génétique et schémas" },
  { value: "general", label: "Autres matières", description: "Apprentissage multidisciplinaire" },
];

export default function EducationDisciplinePicker({
  value,
  onChange,
}: {
  value: EducationDiscipline;
  onChange: (discipline: EducationDiscipline) => void;
}) {
  return (
    <fieldset className="space-y-3">
      <legend className="font-semibold text-lg">Quelle matière souhaites-tu apprendre ?</legend>
      <p className="text-sm text-slate-600">Choisis une matière pour personnaliser la séance.</p>
      <div className="grid gap-3 sm:grid-cols-2" role="radiogroup" aria-label="Matière">
        {OPTIONS.map((option) => (
          <label
            key={option.value}
            className={`cursor-pointer rounded-xl border p-4 focus-within:ring-2 focus-within:ring-blue-600 ${
              value === option.value ? "border-blue-700 bg-blue-50" : "border-slate-200"
            }`}
          >
            <input
              type="radio"
              name="education-discipline"
              value={option.value}
              checked={value === option.value}
              onChange={() => onChange(option.value)}
              className="mr-2 accent-blue-700"
            />
            <span className="font-semibold">{option.label}</span>
            <span className="mt-1 block text-sm text-slate-600">{option.description}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
