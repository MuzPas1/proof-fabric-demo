'use client'

import { useState, useEffect } from 'react'
import { supabase } from '@/lib/supabase'
import { v4 as uuidv4 } from 'uuid'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Shield, FileCheck, Download, PlusCircle, CheckCircle2, XCircle, Loader2 } from 'lucide-react'

// SHA256 hash function
async function sha256(message) {
  const msgBuffer = new TextEncoder().encode(message)
  const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer)
  const hashArray = Array.from(new Uint8Array(hashBuffer))
  const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('')
  return hashHex
}

// Generate random FEA ID
function generateFeaId() {
  return 'FEA-' + uuidv4().substring(0, 8).toUpperCase()
}

export default function App() {
  const [activeTab, setActiveTab] = useState('create')
  
  // Create Transaction State
  const [userId, setUserId] = useState('')
  const [amount, setAmount] = useState('')
  const [createLoading, setCreateLoading] = useState(false)
  const [createResult, setCreateResult] = useState(null)
  
  // Generate Proof State
  const [transactionId, setTransactionId] = useState('')
  const [generateLoading, setGenerateLoading] = useState(false)
  const [generateResult, setGenerateResult] = useState(null)
  
  // Verify Proof State
  const [feaIdVerify, setFeaIdVerify] = useState('')
  const [verifyLoading, setVerifyLoading] = useState(false)
  const [verifyResult, setVerifyResult] = useState(null)
  
  // Export State
  const [feaIdExport, setFeaIdExport] = useState('')
  const [exportLoading, setExportLoading] = useState(false)
  const [exportResult, setExportResult] = useState(null)

  // Create Transaction
  const handleCreateTransaction = async () => {
    if (!userId.trim() || !amount.trim()) {
      setCreateResult({ success: false, message: 'Please fill in all fields' })
      return
    }
    
    setCreateLoading(true)
    setCreateResult(null)
    
    try {
      const id = uuidv4()
      const created_at = new Date().toISOString()
      
      const { data, error } = await supabase
        .from('transactions')
        .insert([{
          id,
          user_id: userId.trim(),
          amount: parseFloat(amount),
          created_at
        }])
        .select()
        .single()
      
      if (error) throw error
      
      setCreateResult({
        success: true,
        message: 'Transaction created successfully!',
        transactionId: data.id
      })
      setUserId('')
      setAmount('')
    } catch (error) {
      console.error('Error creating transaction:', error)
      setCreateResult({ success: false, message: error.message || 'Failed to create transaction' })
    } finally {
      setCreateLoading(false)
    }
  }

  // Generate Proof
  const handleGenerateProof = async () => {
    if (!transactionId.trim()) {
      setGenerateResult({ success: false, message: 'Please enter a transaction ID' })
      return
    }
    
    setGenerateLoading(true)
    setGenerateResult(null)
    
    try {
      // Fetch transaction
      const { data: transaction, error: fetchError } = await supabase
        .from('transactions')
        .select('*')
        .eq('id', transactionId.trim())
        .single()
      
      if (fetchError) throw new Error('Transaction not found')
      
      // Compute hash: SHA256(user_id + "|" + amount + "|" + created_at)
      const hashInput = `${transaction.user_id}|${transaction.amount}|${transaction.created_at}`
      const hash = await sha256(hashInput)
      
      // Generate FEA ID
      const fea_id = generateFeaId()
      
      // Store proof
      const { data: proof, error: insertError } = await supabase
        .from('proofs')
        .insert([{
          id: uuidv4(),
          fea_id,
          transaction_id: transaction.id,
          user_id: transaction.user_id,
          amount: transaction.amount,
          transaction_created_at: transaction.created_at,
          hash,
          proof_status: 'VERIFIED',
          issuer: 'Proof Fabric Protocol v0.1',
          created_at: new Date().toISOString()
        }])
        .select()
        .single()
      
      if (insertError) throw insertError
      
      setGenerateResult({
        success: true,
        message: 'Financial Evidence Artifact generated successfully!',
        feaId: fea_id,
        hash
      })
      setTransactionId('')
    } catch (error) {
      console.error('Error generating proof:', error)
      setGenerateResult({ success: false, message: error.message || 'Failed to generate proof' })
    } finally {
      setGenerateLoading(false)
    }
  }

  // Verify Proof
  const handleVerifyProof = async () => {
    if (!feaIdVerify.trim()) {
      setVerifyResult({ success: false, message: 'Please enter a FEA ID' })
      return
    }
    
    setVerifyLoading(true)
    setVerifyResult(null)
    
    try {
      // Fetch proof
      const { data: proof, error: fetchError } = await supabase
        .from('proofs')
        .select('*')
        .eq('fea_id', feaIdVerify.trim())
        .single()
      
      if (fetchError) throw new Error('FEA not found')
      
      // Recompute hash
      const hashInput = `${proof.user_id}|${proof.amount}|${proof.transaction_created_at}`
      const computedHash = await sha256(hashInput)
      
      const isValid = computedHash === proof.hash
      
      setVerifyResult({
        success: true,
        isValid,
        feaId: proof.fea_id,
        transactionId: proof.transaction_id,
        userId: proof.user_id,
        amount: proof.amount,
        createdAt: proof.transaction_created_at,
        storedHash: proof.hash,
        computedHash,
        issuer: proof.issuer
      })
    } catch (error) {
      console.error('Error verifying proof:', error)
      setVerifyResult({ success: false, message: error.message || 'Failed to verify proof' })
    } finally {
      setVerifyLoading(false)
    }
  }

  // Export FEA
  const handleExportFea = async () => {
    if (!feaIdExport.trim()) {
      setExportResult({ success: false, message: 'Please enter a FEA ID' })
      return
    }
    
    setExportLoading(true)
    setExportResult(null)
    
    try {
      // Fetch proof
      const { data: proof, error: fetchError } = await supabase
        .from('proofs')
        .select('*')
        .eq('fea_id', feaIdExport.trim())
        .single()
      
      if (fetchError) throw new Error('FEA not found')
      
      // Create export data
      const exportData = {
        fea_id: proof.fea_id,
        transaction: {
          id: proof.transaction_id,
          user_id: proof.user_id,
          amount: proof.amount,
          created_at: proof.transaction_created_at
        },
        hash: proof.hash,
        timestamp: proof.created_at,
        proof_status: proof.proof_status,
        issuer: proof.issuer
      }
      
      // Download file
      const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `Financial_Evidence_Artifact_${proof.fea_id}.json`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      
      setExportResult({
        success: true,
        message: `FEA exported successfully: Financial_Evidence_Artifact_${proof.fea_id}.json`
      })
    } catch (error) {
      console.error('Error exporting FEA:', error)
      setExportResult({ success: false, message: error.message || 'Failed to export FEA' })
    } finally {
      setExportLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-950/50 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-6">
          <div className="flex items-center gap-3">
            <Shield className="h-10 w-10 text-blue-500" />
            <div>
              <h1 className="text-2xl font-bold text-white">Proof Fabric Protocol</h1>
              <p className="text-sm text-slate-400">RBI Sandbox Demo — Financial Evidence Artifact System</p>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full max-w-3xl mx-auto">
          <TabsList className="grid w-full grid-cols-4 bg-slate-900/50 border border-slate-800">
            <TabsTrigger value="create" className="data-[state=active]:bg-blue-600 data-[state=active]:text-white">
              <PlusCircle className="h-4 w-4 mr-2" />
              Create
            </TabsTrigger>
            <TabsTrigger value="generate" className="data-[state=active]:bg-blue-600 data-[state=active]:text-white">
              <FileCheck className="h-4 w-4 mr-2" />
              Generate
            </TabsTrigger>
            <TabsTrigger value="verify" className="data-[state=active]:bg-blue-600 data-[state=active]:text-white">
              <Shield className="h-4 w-4 mr-2" />
              Verify
            </TabsTrigger>
            <TabsTrigger value="export" className="data-[state=active]:bg-blue-600 data-[state=active]:text-white">
              <Download className="h-4 w-4 mr-2" />
              Export
            </TabsTrigger>
          </TabsList>

          {/* Create Transaction Tab */}
          <TabsContent value="create">
            <Card className="bg-slate-900/50 border-slate-800">
              <CardHeader>
                <CardTitle className="text-white">Create Transaction</CardTitle>
                <CardDescription className="text-slate-400">
                  Record a new transaction in the system
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="userId" className="text-slate-300">User ID</Label>
                  <Input
                    id="userId"
                    value={userId}
                    onChange={(e) => setUserId(e.target.value)}
                    placeholder="Enter user ID (e.g., USER001)"
                    className="bg-slate-800 border-slate-700 text-white placeholder:text-slate-500"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="amount" className="text-slate-300">Amount (INR)</Label>
                  <Input
                    id="amount"
                    type="number"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    placeholder="Enter amount (e.g., 10000)"
                    className="bg-slate-800 border-slate-700 text-white placeholder:text-slate-500"
                  />
                </div>
                <Button 
                  onClick={handleCreateTransaction} 
                  disabled={createLoading}
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white"
                >
                  {createLoading ? (
                    <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Creating...</>
                  ) : (
                    <><PlusCircle className="h-4 w-4 mr-2" /> Create Transaction</>
                  )}
                </Button>
                
                {createResult && (
                  <div className={`p-4 rounded-lg ${createResult.success ? 'bg-green-900/30 border border-green-700' : 'bg-red-900/30 border border-red-700'}`}>
                    <p className={createResult.success ? 'text-green-400' : 'text-red-400'}>
                      {createResult.message}
                    </p>
                    {createResult.transactionId && (
                      <div className="mt-2 p-3 bg-slate-800 rounded font-mono text-sm text-blue-400">
                        Transaction ID: {createResult.transactionId}
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Generate Proof Tab */}
          <TabsContent value="generate">
            <Card className="bg-slate-900/50 border-slate-800">
              <CardHeader>
                <CardTitle className="text-white">Generate Proof</CardTitle>
                <CardDescription className="text-slate-400">
                  Generate a Financial Evidence Artifact (FEA) for a transaction
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="transactionId" className="text-slate-300">Transaction ID</Label>
                  <Input
                    id="transactionId"
                    value={transactionId}
                    onChange={(e) => setTransactionId(e.target.value)}
                    placeholder="Enter transaction ID"
                    className="bg-slate-800 border-slate-700 text-white placeholder:text-slate-500"
                  />
                </div>
                <Button 
                  onClick={handleGenerateProof} 
                  disabled={generateLoading}
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white"
                >
                  {generateLoading ? (
                    <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Generating...</>
                  ) : (
                    <><FileCheck className="h-4 w-4 mr-2" /> Generate FEA</>
                  )}
                </Button>
                
                {generateResult && (
                  <div className={`p-4 rounded-lg ${generateResult.success ? 'bg-green-900/30 border border-green-700' : 'bg-red-900/30 border border-red-700'}`}>
                    <p className={generateResult.success ? 'text-green-400' : 'text-red-400'}>
                      {generateResult.message}
                    </p>
                    {generateResult.feaId && (
                      <div className="mt-3 space-y-2">
                        <div className="p-4 bg-blue-900/40 border border-blue-600 rounded-lg">
                          <p className="text-slate-400 text-sm">Financial Evidence Artifact ID</p>
                          <p className="text-2xl font-bold text-blue-400 font-mono">{generateResult.feaId}</p>
                        </div>
                        <div className="p-3 bg-slate-800 rounded font-mono text-xs text-slate-400 break-all">
                          SHA256 Hash: {generateResult.hash}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Verify Proof Tab */}
          <TabsContent value="verify">
            <Card className="bg-slate-900/50 border-slate-800">
              <CardHeader>
                <CardTitle className="text-white">Verify Proof</CardTitle>
                <CardDescription className="text-slate-400">
                  Verify a Financial Evidence Artifact (FEA) by recomputing and comparing hashes
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="feaIdVerify" className="text-slate-300">FEA ID</Label>
                  <Input
                    id="feaIdVerify"
                    value={feaIdVerify}
                    onChange={(e) => setFeaIdVerify(e.target.value)}
                    placeholder="Enter FEA ID (e.g., FEA-XXXXXXXX)"
                    className="bg-slate-800 border-slate-700 text-white placeholder:text-slate-500"
                  />
                </div>
                <Button 
                  onClick={handleVerifyProof} 
                  disabled={verifyLoading}
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white"
                >
                  {verifyLoading ? (
                    <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Verifying...</>
                  ) : (
                    <><Shield className="h-4 w-4 mr-2" /> Verify FEA</>
                  )}
                </Button>
                
                {verifyResult && !verifyResult.success && (
                  <div className="p-4 rounded-lg bg-red-900/30 border border-red-700">
                    <p className="text-red-400">{verifyResult.message}</p>
                  </div>
                )}
                
                {verifyResult && verifyResult.success && (
                  <div className="space-y-4">
                    {/* Big verification status */}
                    <div className={`p-6 rounded-lg text-center ${verifyResult.isValid ? 'bg-green-900/30 border-2 border-green-500' : 'bg-red-900/30 border-2 border-red-500'}`}>
                      {verifyResult.isValid ? (
                        <>
                          <CheckCircle2 className="h-16 w-16 text-green-500 mx-auto mb-3" />
                          <p className="text-3xl font-bold text-green-400">✅ FEA Verified</p>
                          <p className="text-green-300 mt-1">Hash integrity confirmed</p>
                        </>
                      ) : (
                        <>
                          <XCircle className="h-16 w-16 text-red-500 mx-auto mb-3" />
                          <p className="text-3xl font-bold text-red-400">❌ FEA Invalid</p>
                          <p className="text-red-300 mt-1">Hash mismatch detected</p>
                        </>
                      )}
                    </div>
                    
                    {/* Details */}
                    <div className="p-4 bg-slate-800 rounded-lg space-y-2">
                      <h4 className="text-white font-semibold mb-3">Verification Details</h4>
                      <div className="grid grid-cols-2 gap-2 text-sm">
                        <span className="text-slate-400">FEA ID:</span>
                        <span className="text-blue-400 font-mono">{verifyResult.feaId}</span>
                        <span className="text-slate-400">Transaction ID:</span>
                        <span className="text-slate-300 font-mono text-xs">{verifyResult.transactionId}</span>
                        <span className="text-slate-400">User ID:</span>
                        <span className="text-slate-300">{verifyResult.userId}</span>
                        <span className="text-slate-400">Amount:</span>
                        <span className="text-slate-300">₹{verifyResult.amount}</span>
                        <span className="text-slate-400">Issuer:</span>
                        <span className="text-slate-300">{verifyResult.issuer}</span>
                      </div>
                      <div className="mt-3 pt-3 border-t border-slate-700">
                        <p className="text-slate-400 text-sm">Stored Hash:</p>
                        <p className="text-slate-300 font-mono text-xs break-all">{verifyResult.storedHash}</p>
                        <p className="text-slate-400 text-sm mt-2">Computed Hash:</p>
                        <p className={`font-mono text-xs break-all ${verifyResult.isValid ? 'text-green-400' : 'text-red-400'}`}>
                          {verifyResult.computedHash}
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Export FEA Tab */}
          <TabsContent value="export">
            <Card className="bg-slate-900/50 border-slate-800">
              <CardHeader>
                <CardTitle className="text-white">Export FEA</CardTitle>
                <CardDescription className="text-slate-400">
                  Download a Financial Evidence Artifact as a JSON file
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="feaIdExport" className="text-slate-300">FEA ID</Label>
                  <Input
                    id="feaIdExport"
                    value={feaIdExport}
                    onChange={(e) => setFeaIdExport(e.target.value)}
                    placeholder="Enter FEA ID (e.g., FEA-XXXXXXXX)"
                    className="bg-slate-800 border-slate-700 text-white placeholder:text-slate-500"
                  />
                </div>
                <Button 
                  onClick={handleExportFea} 
                  disabled={exportLoading}
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white"
                >
                  {exportLoading ? (
                    <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Exporting...</>
                  ) : (
                    <><Download className="h-4 w-4 mr-2" /> Download FEA JSON</>
                  )}
                </Button>
                
                {exportResult && (
                  <div className={`p-4 rounded-lg ${exportResult.success ? 'bg-green-900/30 border border-green-700' : 'bg-red-900/30 border border-red-700'}`}>
                    <p className={exportResult.success ? 'text-green-400' : 'text-red-400'}>
                      {exportResult.message}
                    </p>
                  </div>
                )}
                
                {/* Example output format */}
                <div className="p-4 bg-slate-800 rounded-lg">
                  <p className="text-slate-400 text-sm mb-2">Example Export Format:</p>
                  <pre className="text-xs text-slate-300 font-mono overflow-x-auto">
{`{
  "fea_id": "FEA-XXXXXXXX",
  "transaction": {
    "id": "uuid",
    "user_id": "USER001",
    "amount": 10000,
    "created_at": "2025-01-15T..."
  },
  "hash": "sha256...",
  "timestamp": "2025-01-15T...",
  "proof_status": "VERIFIED",
  "issuer": "Proof Fabric Protocol v0.1"
}`}
                  </pre>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Footer */}
        <footer className="mt-12 text-center text-slate-500 text-sm">
          <p>Proof Fabric Protocol v0.1 — Financial Evidence Artifact (FEA) Generation System</p>
          <p className="mt-1">Built for RBI Sandbox Compliance Demonstration</p>
        </footer>
      </main>
    </div>
  )
}
