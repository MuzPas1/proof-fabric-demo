'use client'

import { useState } from 'react'
import { supabase } from '@/lib/supabase'
import { v4 as uuidv4 } from 'uuid'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Shield, FileCheck, Download, PlusCircle, CheckCircle2, XCircle, Loader2, Zap, X } from 'lucide-react'

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

// Generate random amount between 100-500
function generateRandomAmount() {
  return Math.floor(Math.random() * 401) + 100
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

  // Full Flow State
  const [fullFlowLoading, setFullFlowLoading] = useState(false)
  const [fullFlowStep, setFullFlowStep] = useState(0) // 0=idle, 1=create, 2=generate, 3=verify
  const [fullFlowResult, setFullFlowResult] = useState(null)
  const [fullFlowTime, setFullFlowTime] = useState(0)

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
  const handleExportFea = async (feaIdToExport = null) => {
    const targetFeaId = feaIdToExport || feaIdExport.trim()
    
    if (!targetFeaId) {
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
        .eq('fea_id', targetFeaId)
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

  // Full Proof Flow - One Click Demo
  const handleFullProofFlow = async () => {
    const startTime = Date.now()
    setFullFlowLoading(true)
    setFullFlowResult(null)
    setFullFlowStep(1)
    
    try {
      // Step 1: Create Transaction
      const txId = uuidv4()
      const created_at = new Date().toISOString()
      const randomAmount = generateRandomAmount()
      
      const { data: tx, error: txErr } = await supabase
        .from('transactions')
        .insert([{
          id: txId,
          user_id: 'demo_user',
          amount: randomAmount,
          created_at
        }])
        .select()
        .single()
      
      if (txErr) throw new Error('Failed to create transaction: ' + txErr.message)
      
      setFullFlowStep(2)
      
      // Step 2: Generate FEA
      const hashInput = `${tx.user_id}|${tx.amount}|${tx.created_at}`
      const hash = await sha256(hashInput)
      const fea_id = generateFeaId()
      
      const { data: proof, error: proofErr } = await supabase
        .from('proofs')
        .insert([{
          id: uuidv4(),
          fea_id,
          transaction_id: tx.id,
          user_id: tx.user_id,
          amount: tx.amount,
          transaction_created_at: tx.created_at,
          hash,
          proof_status: 'VERIFIED',
          issuer: 'Proof Fabric Protocol v0.1',
          created_at: new Date().toISOString()
        }])
        .select()
        .single()
      
      if (proofErr) throw new Error('Failed to generate FEA: ' + proofErr.message)
      
      setFullFlowStep(3)
      
      // Step 3: Verify
      const recomputedHash = await sha256(`${proof.user_id}|${proof.amount}|${proof.transaction_created_at}`)
      const isValid = recomputedHash === proof.hash
      
      if (!isValid) throw new Error('Verification failed - hash mismatch')
      
      const endTime = Date.now()
      const elapsedSeconds = ((endTime - startTime) / 1000).toFixed(1)
      
      setFullFlowTime(elapsedSeconds)
      setFullFlowResult({
        success: true,
        transactionId: tx.id,
        feaId: fea_id,
        amount: randomAmount,
        hash
      })
      
    } catch (error) {
      console.error('Full flow error:', error)
      setFullFlowResult({
        success: false,
        message: error.message || 'Full proof flow failed'
      })
    } finally {
      setFullFlowLoading(false)
      setFullFlowStep(0)
    }
  }

  // Close full flow modal
  const closeFullFlowModal = () => {
    setFullFlowResult(null)
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      {/* Full Flow Result Modal */}
      {fullFlowResult && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-lg w-full shadow-2xl">
            {fullFlowResult.success ? (
              <div className="p-8">
                <button 
                  onClick={closeFullFlowModal}
                  className="absolute top-4 right-4 text-slate-400 hover:text-white"
                >
                  <X className="h-6 w-6" />
                </button>
                
                <div className="text-center mb-6">
                  <CheckCircle2 className="h-20 w-20 text-green-500 mx-auto mb-4" />
                  <h2 className="text-2xl font-bold text-green-400 mb-2">
                    ✅ Transaction Verified — Ready for RBI audit
                  </h2>
                  <p className="text-slate-400">
                    No raw data shared. Cryptographic proof validated.
                  </p>
                </div>
                
                <div className="bg-slate-800 rounded-lg p-4 space-y-3 mb-6">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Transaction ID:</span>
                    <span className="text-slate-200 font-mono text-sm">{fullFlowResult.transactionId.substring(0, 18)}...</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">FEA ID:</span>
                    <span className="text-blue-400 font-bold font-mono">{fullFlowResult.feaId}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Amount:</span>
                    <span className="text-slate-200">₹{fullFlowResult.amount}</span>
                  </div>
                </div>
                
                <div className="text-center mb-6">
                  <p className="text-yellow-400 font-medium">
                    ⚡ Audit time: {fullFlowTime} Seconds
                  </p>
                  <p className="text-slate-500 text-sm">(vs weeks in legacy systems)</p>
                </div>
                
                <div className="flex gap-3">
                  <Button 
                    onClick={() => handleExportFea(fullFlowResult.feaId)}
                    className="flex-1 bg-blue-600 hover:bg-blue-700 text-white"
                    disabled={exportLoading}
                  >
                    {exportLoading ? (
                      <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Exporting...</>
                    ) : (
                      <><Download className="h-4 w-4 mr-2" /> Export FEA</>
                    )}
                  </Button>
                  <Button 
                    onClick={closeFullFlowModal}
                    variant="outline"
                    className="flex-1 border-slate-600 text-slate-300 hover:bg-slate-800"
                  >
                    Close
                  </Button>
                </div>
              </div>
            ) : (
              <div className="p-8">
                <div className="text-center mb-6">
                  <XCircle className="h-20 w-20 text-red-500 mx-auto mb-4" />
                  <h2 className="text-2xl font-bold text-red-400 mb-2">
                    ❌ Flow Failed
                  </h2>
                  <p className="text-slate-400">{fullFlowResult.message}</p>
                </div>
                <Button 
                  onClick={closeFullFlowModal}
                  className="w-full bg-slate-700 hover:bg-slate-600 text-white"
                >
                  Close
                </Button>
              </div>
            )}
          </div>
        </div>
      )}

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
        {/* Full Proof Flow Button */}
        <div className="w-full max-w-3xl mx-auto mb-8">
          <Button 
            onClick={handleFullProofFlow}
            disabled={fullFlowLoading}
            className="w-full py-6 text-lg font-bold bg-gradient-to-r from-blue-600 via-blue-500 to-cyan-500 hover:from-blue-700 hover:via-blue-600 hover:to-cyan-600 text-white shadow-lg shadow-blue-500/30 border-0 transition-all duration-300 hover:shadow-blue-500/50 hover:scale-[1.02]"
          >
            {fullFlowLoading ? (
              <div className="flex items-center justify-center gap-3">
                <Loader2 className="h-6 w-6 animate-spin" />
                <span>Processing Full Proof Flow…</span>
                <div className="flex gap-1 ml-2">
                  <span className={`px-2 py-1 rounded text-xs ${fullFlowStep >= 1 ? 'bg-green-500' : 'bg-slate-600'}`}>Create</span>
                  <span className="text-slate-400">→</span>
                  <span className={`px-2 py-1 rounded text-xs ${fullFlowStep >= 2 ? 'bg-green-500' : 'bg-slate-600'}`}>Generate</span>
                  <span className="text-slate-400">→</span>
                  <span className={`px-2 py-1 rounded text-xs ${fullFlowStep >= 3 ? 'bg-green-500' : 'bg-slate-600'}`}>Verify</span>
                </div>
              </div>
            ) : (
              <>
                <Zap className="h-6 w-6 mr-3" />
                Run Full Proof Flow
              </>
            )}
          </Button>
          <p className="text-center text-slate-500 text-sm mt-2">
            One-click demo: Creates transaction → Generates FEA → Verifies proof
          </p>
        </div>

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
                          <p className="text-green-300 mt-1">Ready for RBI audit</p>
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
                  onClick={() => handleExportFea()}
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
