import { Link } from 'react-router'
import { Button } from '@/components/ui/button'

export default function NotFoundPage() {
  return (
    <div className="space-y-4">
      <title>Page not found · Hack the Change</title>
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <p className="text-muted-foreground">There's nothing at this address.</p>
      <Button asChild>
        <Link to="/">Go to your dashboard</Link>
      </Button>
    </div>
  )
}
