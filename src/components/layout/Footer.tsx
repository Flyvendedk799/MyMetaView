export default function Footer() {
  return (
    <footer className="border-t border-line mt-12 py-6">
      <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col md:flex-row justify-between items-center space-y-4 md:space-y-0">
          <div className="text-sm text-secondary-600">
            © {new Date().getFullYear()} MetaView. All rights reserved.
          </div>
          <div className="flex space-x-6 text-sm">
            <a href="/privacy" className="text-secondary-600 hover:text-primary-500 transition-colors">
              Privacy Policy
            </a>
            <a href="/terms" className="text-secondary-600 hover:text-primary-500 transition-colors">
              Terms of Service
            </a>
            <a href="/app/account" className="text-secondary-600 hover:text-primary-500 transition-colors">
              Data & Privacy
            </a>
          </div>
        </div>
      </div>
    </footer>
  )
}
