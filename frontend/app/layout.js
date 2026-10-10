import './globals.css';

export const metadata = {
  title: 'Evidelta',
  description: 'External change intelligence for product and platform signals.',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
