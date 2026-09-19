export default function CausalChain({
  items,
}: {
  items: string[];
}) {
  return (
    <div className="space-y-2">
      {items.map((item, index) => (
        <div key={item}>
          <div className="rounded-lg border border-white/10 bg-[#111113] p-4">
            <p className="text-sm font-medium text-white">
              {item}
            </p>
          </div>

          {index < items.length - 1 && (
            <div className="py-1 text-center text-cyan-400">
              ↓
            </div>
          )}
        </div>
      ))}
    </div>
  );
}