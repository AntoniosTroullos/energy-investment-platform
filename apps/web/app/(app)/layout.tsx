import AppNav from "../../components/AppNav";

export default function AppShellLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <>
      <AppNav />
      {children}
    </>
  );
}
