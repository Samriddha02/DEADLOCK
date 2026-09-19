interface Props {
  title: string;
  value: string | number;
  subtitle: string;
}

export default function StatCard({
  title,
  value,
  subtitle,
}: Props) {
  return (
    <div className="rounded-xl border border-white/10 bg-[#111113] p-5">
      <p className="text-sm text-zinc-500">
        {title}
      </p>

      <p className="mt-2 text-3xl font-bold text-white">
        {value}
      </p>

      <p className="mt-1 text-xs text-zinc-600">
        {subtitle}
      </p>
    </div>
  );
}