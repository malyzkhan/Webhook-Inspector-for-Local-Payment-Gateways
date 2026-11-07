import Inspector from "@/components/Inspector";

export default async function InspectPage({
  params,
}: {
  params: Promise<{ endpointId: string }>;
}) {
  const { endpointId } = await params;
  return <Inspector endpointId={endpointId} />;
}
