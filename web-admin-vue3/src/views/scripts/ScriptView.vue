<template>
  <div class="script-workbench" :style="workbenchStyle">
    <aside v-show="!sidebarCollapsed" class="page-card workbench-sidebar" :style="sidebarStyle">
      <div class="sidebar-topbar">
        <el-button type="primary" plain @click="toggleSidebar">收起左侧</el-button>
      </div>
      <div class="sidebar-section">
        <div class="page-toolbar">
          <div>
            <h2 class="page-title">我的话术模板</h2>
            <p class="page-subtitle">先创建一个话术模板，再为它维护不同的流程版本。</p>
          </div>
          <div class="page-toolbar-right">
            <el-dropdown trigger="click">
              <el-button type="primary" plain>
                导入系统示例
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="importKidsCodingDemo">少儿编程教育推广</el-dropdown-item>
                  <el-dropdown-item @click="importWineTastingDemo">名酒品鉴会邀约</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-button type="primary" @click="openCreateScriptDialog">新建话术模板</el-button>
          </div>
        </div>

        <div class="script-card-list">
          <div
            v-for="item in scripts"
            :key="item.id"
            class="script-card"
            :class="{ 'is-active': activeScript?.id === item.id }"
          >
            <button type="button" class="script-card-main" @click="handleScriptSelect(item)">
              <div class="script-card-head">
                <strong>{{ item.script_name }}</strong>
                <span class="status-chip" :class="resolveStatusClass(item.script_status)">{{ item.script_status }}</span>
              </div>
              <span class="script-card-meta">{{ item.business_type || '未分类业务' }}</span>
              <span class="script-card-meta">{{ item.description || '该模板下可以维护多个流程版本。' }}</span>
            </button>
            <div class="script-card-actions">
              <el-button link type="primary" @click="openEditScriptDialog(item)">编辑</el-button>
              <el-button link type="danger" @click="removeScript(item)">删除</el-button>
            </div>
          </div>
        </div>
      </div>

      <div class="sidebar-section" v-if="activeScript">
        <div class="section-head">
          <div>
            <h3>流程版本</h3>
            <p>{{ activeScript.script_name }}：一个模板下可维护多个版本，便于测试和发布。</p>
          </div>
          <el-button type="primary" plain @click="openCreateVersionDialog">新增流程版本</el-button>
        </div>

        <div class="version-card-list">
          <div
            v-for="item in versions"
            :key="item.id"
            class="version-card"
            :class="{ 'is-active': activeVersion?.id === item.id }"
          >
            <button type="button" class="version-card-main" @click="handleVersionSelect(item)">
              <div class="version-card-head">
                <strong>V{{ item.version_no }}</strong>
                <span class="status-chip" :class="resolveStatusClass(item.version_status)">{{ item.version_status }}</span>
              </div>
              <span>{{ item.version_label }}</span>
              <small>起始节点：{{ item.start_node_code || '尚未设置' }}</small>
            </button>
            <div class="version-card-actions">
              <el-button link type="primary" @click="handleVersionSelect(item)">打开</el-button>
              <el-button link type="danger" @click="removeVersion(item)">删除</el-button>
            </div>
          </div>
        </div>
      </div>

      <div class="sidebar-section" v-if="activeVersion">
        <div class="section-head">
          <div>
            <h3>节点库</h3>
            <p>点击节点类型即可加入画布</p>
          </div>
        </div>

        <div class="palette-list">
          <button
            v-for="templateItem in nodeTemplates"
            :key="templateItem.type"
            type="button"
            class="palette-item"
            :style="{ '--palette-color': templateItem.color }"
            @click="openCreateNodeDialog(templateItem)"
          >
            <strong>{{ templateItem.label }}</strong>
            <span>{{ templateItem.hint }}</span>
          </button>
        </div>
      </div>

      <div class="sidebar-section" v-if="activeVersion">
        <div class="section-head">
          <div>
            <h3>变量库</h3>
            <p>把客户资料、批次字段、自定义变量插入到节点话术中。</p>
          </div>
          <el-button type="primary" plain @click="openVariableDialog">新增变量</el-button>
        </div>

        <div class="variable-list">
          <button
            v-for="variableItem in availableVariables"
            :key="variableItem.key"
            type="button"
            class="variable-chip"
            @click="insertVariableIntoNode(variableItem)"
          >
            <strong>{{ variableItem.label }}</strong>
            <span>{{ buildVariableToken(variableItem.key) }}</span>
          </button>
        </div>
      </div>
    </aside>

    <div v-show="!sidebarCollapsed" class="sidebar-resizer" @mousedown.prevent="startSidebarResize" />

    <section class="page-card flow-stage">
      <div class="flow-topbar">
        <div>
          <h2 class="page-title">话术详情</h2>
          <p class="page-subtitle">
            {{ activeVersion ? `${activeScript?.script_name} / ${activeVersion.version_label}` : '请选择左侧话术版本后编辑流程。' }}
          </p>
          <el-button v-if="sidebarCollapsed" type="primary" plain class="sidebar-expand-button" @click="toggleSidebar">
            展开左侧
          </el-button>
        </div>
        <div class="page-toolbar-right" v-if="activeVersion">
          <el-button type="primary" plain @click="loadScriptDetails">刷新</el-button>
          <el-button type="primary" plain @click="saveCanvasLayout">保存布局</el-button>
          <el-button type="success" @click="publishVersion(activeVersion)">发布版本</el-button>
        </div>
      </div>

      <el-empty v-if="!activeVersion" description="请先选择左侧话术版本" />

      <template v-else>
        <div class="flow-toolbar">
          <div class="toolbar-info">
            <span class="info-pill">节点 {{ nodes.length }}</span>
            <span class="info-pill">连线 {{ edges.length }}</span>
            <span class="info-pill" :class="{ 'is-connecting': dragLinkState.active }">
              {{ dragLinkState.active ? `拖线中：${sourceDragNode?.node_name || '准备连线'}` : '拖拽节点即可调整布局' }}
            </span>
          </div>
          <div class="toolbar-info">
            <span class="zoom-label">缩放</span>
            <el-slider v-model="canvasScalePercent" :min="30" :max="240" :step="10" style="width: 160px" />
            <span class="info-pill">{{ canvasScalePercent }}%</span>
            <span class="board-hint">右侧黄色圆点是输出端，从这里拖出连线；左侧蓝色圆点是输入端，把线拖到这里完成连接。</span>
          </div>
        </div>

        <div class="connection-guide">
          <span class="guide-item">
            <span class="guide-dot is-input"></span>
            左侧蓝点：输入端，只负责接收上一节点连过来的线
          </span>
          <span class="guide-item">
            <span class="guide-dot is-output"></span>
            右侧黄点：输出端，从这里按住拖到目标节点左侧蓝点即可连线，识别分支会按 A-Z 和兜底顺序自动绑定
          </span>
        </div>

        <div class="flow-main">
          <div ref="boardRef" class="flow-board" :class="{ 'is-panning': panState.active }" @mousedown="startBoardPan">
            <div class="flow-board-stage-wrapper" :style="boardStageWrapperStyle">
              <div class="flow-board-stage" :style="boardStageStyle">
                <svg class="flow-lines" :viewBox="boardViewBox" preserveAspectRatio="none">
                  <defs>
                    <marker id="arrow-head" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto">
                      <path d="M0,0 L0,6 L9,3 z" fill="#5c8ff5" />
                    </marker>
                  </defs>
                  <path
                    v-for="item in edgePaths"
                    :key="item.edge.id"
                    class="flow-edge"
                    :class="{ 'is-selected': selectedEdgeId === item.edge.id }"
                    :d="item.path"
                    marker-end="url(#arrow-head)"
                    @click.stop="selectEdge(item.edge)"
                    @dblclick.stop="openEditEdgeDialog(item.edge)"
                  />
                  <g v-for="item in edgePaths" :key="`label_${item.edge.id}`" class="flow-edge-label-group">
                    <rect
                      class="flow-edge-label-bg"
                      :class="{ 'is-selected': selectedEdgeId === item.edge.id }"
                      :x="item.labelX - item.labelWidth / 2"
                      :y="item.labelY - 13"
                      :width="item.labelWidth"
                      height="26"
                      rx="13"
                      @click.stop="selectEdge(item.edge)"
                      @dblclick.stop="openEditEdgeDialog(item.edge)"
                    />
                    <text
                      class="flow-edge-label-text"
                      :class="{ 'is-selected': selectedEdgeId === item.edge.id }"
                      :x="item.labelX"
                      :y="item.labelY + 4"
                      text-anchor="middle"
                      @click.stop="selectEdge(item.edge)"
                      @dblclick.stop="openEditEdgeDialog(item.edge)"
                    >
                      {{ item.label }}
                    </text>
                  </g>
                  <path
                    v-if="previewEdgePath"
                    class="flow-edge is-preview"
                    :d="previewEdgePath"
                    marker-end="url(#arrow-head)"
                  />
                </svg>

                <div
                  v-for="node in nodes"
                  :key="node.id"
                  class="flow-node"
                  :class="[
                    `is-${node.node_type}`,
                    { 'is-connecting': sourceDragNode?.id === node.id, 'is-selected': selectedNodeId === node.id },
                  ]"
                  :style="{ left: `${node.position_x}px`, top: `${node.position_y}px` }"
                  @mousedown="startNodeDrag($event, node)"
                  @click.stop="selectNode(node)"
                  @dblclick.stop="openEditNodeDialog(node)"
                >
                  <button
                    type="button"
                    class="node-handle is-input"
                    @mousedown.stop.prevent="prepareInputHandle(node)"
                    @mouseup.stop.prevent="finishEdgeDrag(node)"
                  />
                  <div class="flow-node-head">
                    <span>{{ resolveNodeLabel(node.node_type) }}</span>
                    <button type="button" class="node-delete" @click.stop="removeNode(node)">×</button>
                  </div>
                  <div class="flow-node-body">
                    <strong>{{ node.node_name }}</strong>
                    <p>{{ resolveNodePreview(node) }}</p>
                  </div>
                  <div class="flow-node-foot">
                    <span>{{ formatNodeCodePreview(node.node_code) }}</span>
                    <span v-if="activeVersion.start_node_code === node.node_code" class="start-tag">起始</span>
                  </div>
                  <button type="button" class="node-handle is-output" @mousedown.stop="startEdgeDrag($event, node)" />
                </div>
              </div>
            </div>
          </div>

          <aside class="flow-inspector">
            <div class="inspector-section">
              <div class="section-head">
                <div>
                  <h3>当前节点</h3>
                  <p>单击节点可查看或编辑</p>
                </div>
              </div>
              <div v-if="selectedNode" class="inspector-card">
                <strong>{{ selectedNode.node_name }}</strong>
                <span>类型：{{ resolveNodeLabel(selectedNode.node_type) }}</span>
                <span :title="selectedNode.node_code">编码：{{ formatNodeCodePreview(selectedNode.node_code) }}</span>
                <span>坐标：{{ Math.round(selectedNode.position_x) }}, {{ Math.round(selectedNode.position_y) }}</span>
                <div class="inspector-actions">
                  <el-button type="primary" plain @click="openEditNodeDialog(selectedNode)">编辑节点</el-button>
                  <el-button type="danger" plain @click="removeNode(selectedNode)">删除节点</el-button>
                  <el-button type="success" plain @click="setStartNode(selectedNode)">设为起始</el-button>
                </div>
              </div>
              <el-empty v-else description="请在画布中选择节点" />
            </div>

            <div class="inspector-section">
              <div class="section-head">
                <div>
                  <h3>当前连线</h3>
                  <p>单击连线可查看，双击连线或点击下方按钮可直接修改。</p>
                </div>
              </div>
              <div v-if="selectedEdge" class="inspector-card">
                <strong>{{ resolveEdgeLabel(selectedEdge) }}</strong>
                <span>起点：{{ resolveNodeNameByCode(selectedEdge.from_node_code) }}</span>
                <span>终点：{{ resolveNodeNameByCode(selectedEdge.to_node_code) }}</span>
                <span>类型：{{ selectedEdge.condition_type }}</span>
                <div class="inspector-actions">
                  <el-button type="primary" plain @click="openEditEdgeDialog(selectedEdge)">编辑连线</el-button>
                  <el-button type="danger" plain @click="confirmRemoveEdge(selectedEdge)">删除连线</el-button>
                </div>
              </div>
              <el-empty v-else description="请在画布中选择连线" />
            </div>
          </aside>
        </div>
      </template>
    </section>

    <el-dialog v-model="scriptDialogVisible" :title="scriptDialogMode === 'create' ? '新建话术模板' : '编辑话术模板'" width="640px">
      <el-form :model="scriptForm" label-width="100px">
        <el-form-item label="话术名称">
          <el-input v-model="scriptForm.script_name" />
        </el-form-item>
        <el-form-item label="业务类型">
          <el-input v-model="scriptForm.business_type" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="scriptForm.description" type="textarea" :rows="4" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="scriptDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submittingScript" @click="submitScript">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="versionDialogVisible" title="新增流程版本" width="620px">
      <el-form :model="versionForm" label-width="100px">
        <el-form-item label="版本号">
          <el-input-number v-model="versionForm.version_no" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="版本标签">
          <el-input v-model="versionForm.version_label" />
        </el-form-item>
        <el-form-item label="说明">
          <div class="dialog-hint">同一个话术模板可以有多个流程版本，比如“测试版”“正式版”“房产A版”。</div>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="versionForm.remark" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="versionDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submittingVersion" @click="submitVersion">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="nodeDialogVisible" :title="nodeDialogMode === 'create' ? '新增节点' : '编辑节点'" width="700px">
        <el-form :model="nodeForm" label-width="100px">
          <el-form-item label="节点编码">
          <div class="node-form-stack">
            <el-input v-model="nodeForm.node_code" disabled />
            <div class="dialog-hint">节点编码由系统自动生成，避免重复冲突。</div>
          </div>
        </el-form-item>
        <el-form-item label="节点名称">
          <el-input v-model="nodeForm.node_name" />
        </el-form-item>
        <el-form-item label="节点类型">
          <el-select v-model="nodeForm.node_type" style="width: 100%" @change="handleNodeTypeChange">
            <el-option v-for="item in nodeTemplates" :key="item.type" :label="item.label" :value="item.type" />
          </el-select>
        </el-form-item>
        <template v-if="isPlaybackNodeType(nodeForm.node_type)">
          <el-form-item label="播报文案">
            <el-input
              v-model="nodeForm.prompt_text"
              type="textarea"
              :rows="4"
              placeholder="这里填写播报内容，可插入客户姓名、手机号等变量。"
            />
          </el-form-item>
          <el-form-item label="语音方式">
            <el-radio-group v-model="nodeForm.playback_source">
              <el-radio-button label="local">本地语音</el-radio-button>
              <el-radio-button label="tts">在线生成</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="本地录音" v-if="nodeForm.playback_source === 'local'">
            <div class="node-form-stack">
              <el-select v-model="nodeForm.audio_asset_id" clearable filterable style="width: 100%" placeholder="请选择本地录音库中的音频">
                <el-option
                  v-for="asset in localAudioAssetOptions"
                  :key="asset.id"
                  :label="buildAudioAssetLabel(asset)"
                  :value="asset.id"
                />
              </el-select>
              <div class="dialog-hint">
                优先使用已经录好的本地语音，避免重复产生在线 TTS 费用。
              </div>
            </div>
          </el-form-item>
          <el-form-item label="TTS方案">
            <div class="node-form-stack">
              <el-select
                v-model="nodeForm.tts_provider_id"
                clearable
                filterable
                style="width: 100%"
                placeholder="请选择后台已配置好的 TTS 接口"
              >
                <el-option
                  v-for="provider in ttsProviderOptions"
                  :key="provider.id"
                  :label="provider.provider_name"
                  :value="provider.id"
                />
              </el-select>
              <el-select
                v-model="nodeForm.tts_voice_profile"
                clearable
                filterable
                style="width: 100%"
                placeholder="请选择音色方案"
              >
                <el-option
                  v-for="profile in currentTtsVoiceProfiles"
                  :key="profile.value"
                  :label="profile.label"
                  :value="profile.value"
                />
              </el-select>
              <div class="dialog-hint">
                音色 ID、音调、声音 ID、语速等高级参数统一在后台 TTS 接口配置中维护，这里只选方案。
              </div>
            </div>
          </el-form-item>
          <el-form-item label="快捷生成" v-if="nodeForm.playback_source === 'local'">
            <div class="node-form-stack">
              <el-button type="primary" plain @click="generateLocalAudioAssetFromPrompt">根据当前文案生成一条本地录音</el-button>
              <div class="dialog-hint">
                当前会先把播报文案和 TTS 方案写入本地录音库，后续接入真实 TTS 执行器后可直接复用这条记录。
              </div>
            </div>
          </el-form-item>
          <el-form-item label="兜底动作" v-if="nodeForm.node_type === 'fallback'">
            <el-input v-model="nodeForm.fallback_action" placeholder="例如 重播一次并结束" />
          </el-form-item>
        </template>
        <template v-else-if="nodeForm.node_type === 'asr'">
          <el-form-item label="识别分支">
            <div class="asr-branch-editor">
              <div v-for="branchItem in nodeForm.asr_branch_items" :key="branchItem.route_code" class="asr-branch-card">
                <div class="asr-branch-head">
                  <strong>{{ branchItem.route_code }} 分支</strong>
                  <el-button
                    link
                    type="danger"
                    :disabled="nodeForm.asr_branch_items.length <= 1"
                    @click="removeAsrBranch(branchItem.route_code)"
                  >
                    删除
                  </el-button>
                </div>
                <el-input v-model="branchItem.branch_name" placeholder="分支名称，例如 强意向、价格咨询、需要回访" />
                <el-input
                  v-model="branchItem.keywords_text"
                  type="textarea"
                  :rows="3"
                  placeholder="请输入该分支的关键词，支持逗号或换行分隔"
                />
              </div>
              <el-button type="primary" plain :disabled="nodeForm.asr_branch_items.length >= routeCodeOptions.length" @click="addAsrBranch">
                新增分支
              </el-button>
              <div class="dialog-hint">识别分支支持从 A 到 Z 动态扩展，适合复杂业务场景。</div>
            </div>
          </el-form-item>
          <el-form-item label="兜底说明">
            <el-input
              v-model="nodeForm.asr_default_branch_text"
              placeholder="当所有自定义分支都未命中、超时或静音时走这里"
            />
          </el-form-item>
          <el-form-item label="超时秒数">
            <el-input-number v-model="nodeForm.asr_timeout_seconds" :min="1" :max="60" style="width: 100%" />
          </el-form-item>
          <el-form-item label="断句静音毫秒">
            <el-input-number v-model="nodeForm.asr_sentence_silence_ms" :min="100" :max="3000" :step="50" style="width: 100%" />
            <div class="dialog-hint">控制单句在静音多久后视为说完，建议 300 到 600 毫秒。</div>
          </el-form-item>
        </template>
        <el-form-item label="变量快捷插入" v-if="isPlaybackNodeType(nodeForm.node_type)">
          <div class="node-variable-list">
            <button
              v-for="variableItem in availableVariables"
              :key="variableItem.key"
              type="button"
              class="variable-chip"
              @click="insertVariableIntoNode(variableItem)"
            >
              <strong>{{ variableItem.label }}</strong>
              <span>{{ buildVariableToken(variableItem.key) }}</span>
            </button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="nodeDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submittingNode" @click="submitNode">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="edgeDialogVisible" :title="edgeDialogMode === 'create' ? '新增连线' : '编辑连线'" width="680px">
      <el-form :model="edgeForm" label-width="100px">
        <el-form-item label="起始节点">
          <el-input v-model="edgeForm.from_node_code" disabled />
        </el-form-item>
        <el-form-item label="目标节点" v-if="edgeDialogMode === 'create'">
          <el-input v-model="edgeForm.to_node_code" disabled />
        </el-form-item>
        <el-form-item label="目标节点" v-else>
          <el-select v-model="edgeForm.to_node_code" style="width: 100%">
            <el-option
              v-for="item in availableEdgeTargetNodes"
              :key="item.node_code"
              :label="item.node_name"
              :value="item.node_code"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="自动分支" v-if="isRecognizeEdgeForm">
          <el-select v-model="edgeForm.route_code" style="width: 100%">
            <el-option
              v-for="optionItem in recognizeRouteOptions"
              :key="optionItem.value"
              :label="optionItem.label"
              :value="optionItem.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="条件类型" v-else>
          <el-select v-model="edgeForm.condition_type" style="width: 100%">
            <el-option v-for="item in edgeConditionOptions" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
        <el-form-item label="条件配置" v-if="!isRecognizeEdgeForm">
          <el-input v-model="edgeForm.condition_config_text" type="textarea" :rows="6" />
        </el-form-item>
        <el-form-item label="说明" v-else>
          <div class="dialog-hint">连线完成后请选择这条线对应哪个识别分支，未命中场景请选择兜底分支。连线排序由系统自动处理。</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="closeEdgeDialog">取消</el-button>
        <el-button type="primary" :loading="submittingEdge" @click="submitEdge">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="variableDialogVisible" title="新增自定义变量" width="560px">
      <el-form :model="variableForm" label-width="100px">
        <el-form-item label="变量名称">
          <el-input v-model="variableForm.label" placeholder="例如 客户姓名" />
        </el-form-item>
        <el-form-item label="变量键名">
          <el-input v-model="variableForm.key" placeholder="例如 customer_name" />
        </el-form-item>
        <el-form-item label="示例值">
          <el-input v-model="variableForm.example" placeholder="例如 张三" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="variableDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitVariable">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  createKidsCodingDemoApi,
  createWineTastingDemoApi,
  createScriptApi,
  createScriptEdgeApi,
  createScriptNodeApi,
  createScriptVersionApi,
  deleteScriptApi,
  deleteScriptVersionApi,
  deleteScriptEdgeApi,
  deleteScriptNodeApi,
  fetchAudioAssetsApi,
  fetchProvidersApi,
  fetchScriptEdgesApi,
  fetchScriptNodesApi,
  fetchScriptsApi,
  fetchScriptVersionsApi,
  publishScriptVersionApi,
  updateScriptApi,
  updateScriptEdgeApi,
  updateScriptNodeApi,
  updateScriptVersionApi,
  generateTtsAudioAssetApi,
} from '@/api/modules'
import { formatJson, parseJsonText, resolveStatusClass } from '@/utils/format'

const scripts = ref([])
const versions = ref([])
const nodes = ref([])
const edges = ref([])
const audioAssets = ref([])
const providers = ref([])
const activeScript = ref(null)
const activeVersion = ref(null)
const selectedNodeId = ref(null)
const selectedEdgeId = ref(null)
const boardRef = ref(null)
const canvasScalePercent = ref(100)
const sidebarWidth = ref(340)
const sidebarCollapsed = ref(false)

const scriptDialogVisible = ref(false)
const scriptDialogMode = ref('create')
const submittingScript = ref(false)
const editingScriptId = ref(null)
const scriptForm = reactive(createDefaultScriptForm())

const versionDialogVisible = ref(false)
const submittingVersion = ref(false)
const versionForm = reactive(createDefaultVersionForm())

const nodeDialogVisible = ref(false)
const nodeDialogMode = ref('create')
const submittingNode = ref(false)
const editingNodeId = ref(null)
const pendingNodePosition = ref({ x: 120, y: 120 })
const nodeForm = reactive(createDefaultNodeForm())

const edgeDialogVisible = ref(false)
const edgeDialogMode = ref('create')
const submittingEdge = ref(false)
const editingEdgeId = ref(null)
const edgeForm = reactive(createDefaultEdgeForm())

const variableDialogVisible = ref(false)
const variableForm = reactive(createDefaultVariableForm())

const dragState = reactive({
  nodeId: null,
  offsetX: 0,
  offsetY: 0,
  active: false,
})

const dragLinkState = reactive({
  active: false,
  sourceNodeId: null,
  currentX: 0,
  currentY: 0,
})
const panState = reactive({
  active: false,
  startClientX: 0,
  startClientY: 0,
  startScrollLeft: 0,
  startScrollTop: 0,
})
const sidebarResizeState = reactive({
  active: false,
  startClientX: 0,
  startWidth: 340,
})

const nodeTemplates = [
  { type: 'start', label: '开场白', color: '#8b76ff', hint: '用于话术进入时的第一句播报。' },
  { type: 'playback', label: '播报节点', color: '#4fa8ff', hint: '适合固定话术、录音或变量播报。' },
  { type: 'asr', label: '识别分支', color: '#32b3a7', hint: '在一个节点里配置 A-Z 多个识别分支和兜底结果。' },
  { type: 'end', label: '结束节点', color: '#5a6c8f', hint: '流程结束或挂机收尾。' },
]
const edgeConditionOptions = ['always', 'keyword', 'nomatch']
const routeCodeOptions = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('')
const builtinVariables = [
  { key: 'customer_name', label: '客户姓名', example: '张三', builtin: true },
  { key: 'mobile', label: '手机号', example: '13800138000', builtin: true },
  { key: 'batch_name', label: '批次名称', example: '四月房产名单', builtin: true },
  { key: 'task_name', label: '任务名称', example: '房产外呼测试', builtin: true },
  { key: 'ext.company', label: '扩展字段:公司', example: '示例科技', builtin: true },
]
const playbackNodeTypes = new Set(['start', 'playback', 'end'])

const selectedNode = computed(() => nodes.value.find((item) => item.id === selectedNodeId.value) || null)
const selectedEdge = computed(() => edges.value.find((item) => item.id === selectedEdgeId.value) || null)
const sourceDragNode = computed(() => nodes.value.find((item) => item.id === dragLinkState.sourceNodeId) || null)
const boardWidth = 3200
const boardHeight = 3600
const boardViewBox = computed(() => `0 0 ${boardWidth} ${boardHeight}`)
const edgePaths = computed(() => buildEdgePaths(nodes.value, edges.value))
const previewEdgePath = computed(() => buildPreviewEdgePath(sourceDragNode.value, dragLinkState))
const canvasScale = computed(() => canvasScalePercent.value / 100)
const boardStageWrapperStyle = computed(() => ({
  width: `${Math.round(boardWidth * canvasScale.value)}px`,
  height: `${Math.round(boardHeight * canvasScale.value)}px`,
}))
const boardStageStyle = computed(() => ({
  transform: `scale(${canvasScale.value})`,
  transformOrigin: 'top left',
}))
const workbenchStyle = computed(() => ({
  gridTemplateColumns: sidebarCollapsed.value ? '1fr' : `${sidebarWidth.value}px 10px minmax(0, 1fr)`,
}))
const sidebarStyle = computed(() => ({
  width: `${sidebarWidth.value}px`,
}))
const customVariables = computed(() => activeVersion.value?.canvas_json?.custom_variables || [])
const availableVariables = computed(() => [...builtinVariables, ...customVariables.value])
const localAudioAssetOptions = computed(() =>
  audioAssets.value.filter((item) => item.storage_backend === 'local' && item.asset_status === 'active'),
)
const ttsProviderOptions = computed(() =>
  providers.value.filter((item) => item.provider_type === 'tts' && item.is_enabled),
)
const currentTtsVoiceProfiles = computed(() => resolveProviderVoiceProfiles(nodeForm.tts_provider_id))
const isRecognizeEdgeForm = computed(() => {
  const fromNode = nodes.value.find((item) => item.node_code === edgeForm.from_node_code)
  return fromNode?.node_type === 'asr'
})
const recognizeRouteOptions = computed(() => {
  const sourceNode = nodes.value.find((item) => item.node_code === edgeForm.from_node_code) || null
  if (!sourceNode || sourceNode.node_type !== 'asr') {
    return []
  }
  return [
    ...resolveRecognizeBranches(sourceNode).map((item) => ({
      value: item.route_code,
      label: resolveRecognizeRouteLabelByCode(item.route_code, sourceNode),
    })),
    {
      value: 'DEFAULT',
      label: resolveRecognizeRouteLabelByCode('DEFAULT', sourceNode),
    },
  ]
})
const availableEdgeTargetNodes = computed(() =>
  nodes.value.filter((item) => item.node_code !== edgeForm.from_node_code),
)

/**
 * 创建话术表单默认值。
 *
 * @returns {object} 返回默认话术表单对象。
 */
function createDefaultScriptForm() {
  return {
    script_name: '',
    business_type: '',
    description: '',
    script_status: 'draft',
  }
}

/**
 * 创建版本表单默认值。
 *
 * @returns {object} 返回默认版本表单对象。
 */
function createDefaultVersionForm() {
  return {
    version_no: 1,
    version_label: '',
    remark: '',
  }
}

/**
 * 创建节点表单默认值。
 *
 * @returns {object} 返回默认节点表单对象。
 */
function createDefaultNodeForm() {
  return {
    node_code: '',
    node_name: '',
    node_type: 'start',
    prompt_text: '',
    playback_source: 'tts',
    audio_asset_id: null,
    tts_provider_id: null,
    tts_voice_profile: '',
    asr_branch_items: createDefaultAsrBranchItems(),
    asr_default_branch_text: '未识别/超时/静音',
    asr_timeout_seconds: 5,
    asr_sentence_silence_ms: 400,
  }
}

/**
 * 创建自定义变量表单默认值。
 *
 * @returns {object} 返回默认变量表单对象。
 */
function createDefaultVariableForm() {
  return {
    key: '',
    label: '',
    example: '',
  }
}

/**
 * 创建连线表单默认值。
 *
 * @returns {object} 返回默认连线表单对象。
 */
function createDefaultEdgeForm() {
  return {
    edge_code: '',
    from_node_code: '',
    to_node_code: '',
    condition_type: 'always',
    condition_config_text: '{}',
    route_code: 'A',
    sort_order: 100,
  }
}

/**
 * 创建识别分支默认数组，供识别节点初始化使用。
 *
 * @returns {Array<object>} 返回默认识别分支数组。
 */
function createDefaultAsrBranchItems() {
  return [
    { route_code: 'A', branch_name: '正向意向', keywords_text: '是，可以，好啊，好的' },
    { route_code: 'B', branch_name: '拒绝/异议', keywords_text: '不要，挂机，不需要' },
  ]
}

/**
 * 将识别节点配置统一转换为分支数组，兼容旧版 A/B/C 结构。
 *
 * @param {object} nodeConfig 节点配置对象。
 * @returns {Array<object>} 返回标准化后的识别分支数组。
 */
function normalizeAsrBranchItems(nodeConfig) {
  const branchItems = Array.isArray(nodeConfig?.asr_branches) ? nodeConfig.asr_branches : []
  if (branchItems.length) {
    return branchItems
      .map((item, index) => {
        const routeCode = String(item.route_code || routeCodeOptions[index] || '').toUpperCase()
        if (!routeCodeOptions.includes(routeCode)) {
          return null
        }
        return {
          route_code: routeCode,
          branch_name: String(item.branch_name || item.label || `${routeCode}分支`),
          keywords_text: Array.isArray(item.keywords) ? item.keywords.join('，') : String(item.keywords_text || ''),
        }
      })
      .filter(Boolean)
  }
  const legacyBranchItems = []
  if (Array.isArray(nodeConfig?.branch_a_keywords)) {
    legacyBranchItems.push({
      route_code: 'A',
      branch_name: 'A分支',
      keywords_text: nodeConfig.branch_a_keywords.join('，'),
    })
  }
  if (Array.isArray(nodeConfig?.branch_b_keywords)) {
    legacyBranchItems.push({
      route_code: 'B',
      branch_name: 'B分支',
      keywords_text: nodeConfig.branch_b_keywords.join('，'),
    })
  }
  return legacyBranchItems.length ? legacyBranchItems : createDefaultAsrBranchItems()
}

/**
 * 解析识别节点的兜底分支说明，兼容旧版配置结构。
 *
 * @param {object} nodeConfig 节点配置对象。
 * @returns {string} 返回兜底分支说明文本。
 */
function resolveAsrDefaultBranchText(nodeConfig) {
  return String(nodeConfig?.default_branch_label || nodeConfig?.branch_c_label || '未识别/超时/静音')
}

/**
 * 根据当前节点和连线生成 SVG 路径列表。
 *
 * @param {Array<object>} nodeItems 当前画布节点数组。
 * @param {Array<object>} edgeItems 当前画布连线数组。
 * @returns {Array<object>} 返回适合模板循环的路径对象数组。
 */
function buildEdgePaths(nodeItems, edgeItems) {
  const nodeMap = new Map(nodeItems.map((item) => [item.node_code, item]))
  return edgeItems
    .map((edge) => {
      const fromNode = nodeMap.get(edge.from_node_code)
      const toNode = nodeMap.get(edge.to_node_code)
      if (!fromNode || !toNode) {
        return null
      }
      const startX = fromNode.position_x + 220
      const startY = fromNode.position_y + 74
      const endX = toNode.position_x
      const endY = toNode.position_y + 74
      const label = resolveEdgeLabel(edge)
      return {
        edge,
        path: buildBezierPath(startX, startY, endX, endY),
        label,
        labelX: calculateBezierMidpoint(startX, endX),
        labelY: calculateBezierLabelY(startY, endY),
        labelWidth: Math.max(68, label.length * 14 + 18),
      }
    })
    .filter(Boolean)
}

/**
 * 根据当前拖线状态生成预览曲线路径。
 *
 * @param {object | null} sourceNode 当前拖线起始节点对象。
 * @param {{active: boolean, currentX: number, currentY: number}} currentDragState 当前拖线状态对象。
 * @returns {string} 返回 SVG 路径字符串；未拖线时返回空字符串。
 */
function buildPreviewEdgePath(sourceNode, currentDragState) {
  if (!sourceNode || !currentDragState.active) {
    return ''
  }
  return buildBezierPath(
    sourceNode.position_x + 220,
    sourceNode.position_y + 74,
    currentDragState.currentX,
    currentDragState.currentY,
  )
}

/**
 * 构造统一的贝塞尔曲线路径字符串。
 *
 * @param {number} startX 起点 X 坐标。
 * @param {number} startY 起点 Y 坐标。
 * @param {number} endX 终点 X 坐标。
 * @param {number} endY 终点 Y 坐标。
 * @returns {string} 返回 SVG 路径字符串。
 */
function buildBezierPath(startX, startY, endX, endY) {
  const middleX = (startX + endX) / 2
  return `M ${startX} ${startY} C ${middleX} ${startY}, ${middleX} ${endY}, ${endX} ${endY}`
}

/**
 * 计算贝塞尔曲线中部的标签 X 坐标。
 *
 * @param {number} startX 起点 X 坐标。
 * @param {number} endX 终点 X 坐标。
 * @returns {number} 返回标签中点的 X 坐标。
 */
function calculateBezierMidpoint(startX, endX) {
  return (startX + endX) / 2
}

/**
 * 计算连线标签的 Y 坐标，避免与节点边缘和箭头重叠。
 *
 * @param {number} startY 起点 Y 坐标。
 * @param {number} endY 终点 Y 坐标。
 * @returns {number} 返回标签显示的 Y 坐标。
 */
function calculateBezierLabelY(startY, endY) {
  const middleY = (startY + endY) / 2
  if (Math.abs(startY - endY) < 24) {
    return middleY - 22
  }
  return middleY
}

/**
 * 判断指定节点类型是否属于播报类节点。
 *
 * @param {string} nodeType 当前节点类型值。
 * @returns {boolean} 播报类节点返回 `true`，否则返回 `false`。
 */
function isPlaybackNodeType(nodeType) {
  return playbackNodeTypes.has(nodeType)
}

/**
 * 构建音频资源下拉框展示文本。
 *
 * @param {object} asset 当前音频资源对象。
 * @returns {string} 返回适合下拉框显示的文本。
 */
function buildAudioAssetLabel(asset) {
  const durationText = asset.duration_ms ? ` / ${Math.round(asset.duration_ms / 1000)}秒` : ''
  return `${asset.asset_name}${durationText}`
}

/**
 * 加载本地录音库资源，供节点编辑时直接选择。
 *
 * @returns {Promise<void>} 返回音频资源加载完成后的 Promise。
 */
async function loadAudioAssets() {
  audioAssets.value = await fetchAudioAssetsApi()
}

/**
 * 加载后台已配置的接口列表，供节点编辑时选择 TTS 方案。
 *
 * @returns {Promise<void>} 返回接口列表加载完成后的 Promise。
 */
async function loadProviders() {
  providers.value = await fetchProvidersApi()
}

/**
 * 根据接口配置解析可用的音色方案列表。
 *
 * @param {number | null} providerId 当前选中的接口主键。
 * @returns {Array<{label: string, value: string}>} 返回音色方案数组。
 */
function resolveProviderVoiceProfiles(providerId) {
  const providerItem = ttsProviderOptions.value.find((item) => item.id === providerId)
  if (!providerItem) {
    return []
  }
  const profileSource =
    providerItem.config_json?.voice_profiles ||
    providerItem.config_json?.voices ||
    providerItem.config_json?.voice_options ||
    []
  if (!Array.isArray(profileSource)) {
    return []
  }
  return profileSource
    .map((item, index) => {
      if (typeof item === 'string') {
        return { label: item, value: item }
      }
      const value = String(item.value || item.profile_id || item.voice_id || item.code || item.id || index)
      const label = String(item.label || item.profile_name || item.voice_name || item.name || value)
      return { label, value }
    })
    .filter((item) => item.value)
}

/**
 * 将节点配置对象转换为当前页面使用的表单结构。
 *
 * @param {object} node 当前要编辑的节点对象。
 * @returns {object} 返回已经拆分好的节点表单对象。
 */
function buildNodeFormFromNode(node) {
  const nodeConfig = node?.node_config || {}
  return {
    node_code: node.node_code || '',
    node_name: node.node_name || '',
    node_type: node.node_type || 'start',
    prompt_text: String(nodeConfig.prompt || ''),
    playback_source: nodeConfig.playback_source || (nodeConfig.use_tts === false ? 'local' : 'tts'),
    audio_asset_id: node.audio_asset_id || null,
    tts_provider_id: nodeConfig.tts_provider_id || null,
    tts_voice_profile: nodeConfig.tts_voice_profile || '',
    asr_branch_items: normalizeAsrBranchItems(nodeConfig),
    asr_default_branch_text: resolveAsrDefaultBranchText(nodeConfig),
    asr_timeout_seconds: Number(nodeConfig.timeout_seconds || 5),
    asr_sentence_silence_ms: Number(nodeConfig.sentence_silence_ms || nodeConfig.max_sentence_silence || 400),
  }
}

/**
 * 将当前节点表单转换为后端保存所需的配置对象。
 *
 * @returns {object} 返回可直接提交给后端的节点配置对象。
 */
function buildNodeConfigFromForm() {
  if (isPlaybackNodeType(nodeForm.node_type)) {
    return {
      prompt: nodeForm.prompt_text.trim(),
      playback_source: nodeForm.playback_source,
      use_tts: nodeForm.playback_source === 'tts',
      tts_provider_id: nodeForm.tts_provider_id || null,
      tts_voice_profile: nodeForm.tts_voice_profile || null,
      action: nodeForm.node_type === 'fallback' ? nodeForm.fallback_action.trim() : null,
    }
  }
  if (nodeForm.node_type === 'asr') {
    return {
      asr_branches: nodeForm.asr_branch_items.map((item) => ({
        route_code: item.route_code,
        branch_name: item.branch_name.trim() || `${item.route_code}分支`,
        keywords: splitInputTokens(item.keywords_text),
      })),
      default_branch_label: nodeForm.asr_default_branch_text.trim() || '未识别/超时/静音',
      timeout_seconds: Number(nodeForm.asr_timeout_seconds || 5),
      sentence_silence_ms: Number(nodeForm.asr_sentence_silence_ms || 400),
    }
  }
  return {}
}

/**
 * 将逗号或换行分隔的文本拆成数组。
 *
 * @param {string} rawText 原始输入文本。
 * @returns {string[]} 返回去空白后的字符串数组。
 */
function splitInputTokens(rawText) {
  return String(rawText || '')
    .split(/[\n,，]+/)
    .map((item) => item.trim())
    .filter(Boolean)
}

/**
 * 根据识别节点配置返回可用分支数组，兼容旧版 A/B 结构。
 *
 * @param {object | null} sourceNode 起始识别节点对象。
 * @returns {Array<object>} 返回标准化后的识别分支数组。
 */
function resolveRecognizeBranches(sourceNode) {
  if (!sourceNode || sourceNode.node_type !== 'asr') {
    return []
  }
  return normalizeAsrBranchItems(sourceNode.node_config || {}).map((item) => ({
    route_code: item.route_code,
    branch_name: item.branch_name,
    keywords: splitInputTokens(item.keywords_text),
  }))
}

/**
 * 根据分支代号返回识别分支展示文本。
 *
 * @param {string} routeCode 当前分支代号。
 * @param {object | null} sourceNode 起始识别节点对象，可为空。
 * @returns {string} 返回适合界面展示的分支文本。
 */
function resolveRecognizeRouteLabelByCode(routeCode, sourceNode = null) {
  if (routeCode === 'DEFAULT') {
    const defaultText = sourceNode ? resolveAsrDefaultBranchText(sourceNode.node_config || {}) : '兜底分支'
    return `兜底分支：${defaultText}`
  }
  const branchItem = resolveRecognizeBranches(sourceNode).find((item) => item.route_code === routeCode)
  if (branchItem) {
    return `${routeCode} 分支：${branchItem.branch_name}`
  }
  if (routeCodeOptions.includes(routeCode)) {
    return `${routeCode} 分支`
  }
  return routeCode || '默认流转'
}

/**
 * 判断两个字符串数组在顺序无关的情况下是否一致。
 *
 * @param {string[]} leftItems 左侧数组。
 * @param {string[]} rightItems 右侧数组。
 * @returns {boolean} 一致返回 `true`，否则返回 `false`。
 */
function arrayEquals(leftItems, rightItems) {
  const normalizedLeft = [...leftItems].map((item) => String(item)).sort()
  const normalizedRight = [...rightItems].map((item) => String(item)).sort()
  if (normalizedLeft.length !== normalizedRight.length) {
    return false
  }
  return normalizedLeft.every((item, index) => item === normalizedRight[index])
}

/**
 * 加载话术列表。
 *
 * @returns {Promise<void>} 返回列表加载完成后的 Promise。
 */
async function loadScripts() {
  scripts.value = await fetchScriptsApi()
  if (!activeScript.value && scripts.value.length) {
    activeScript.value = scripts.value[0]
    await loadScriptDetails()
  }
}

/**
 * 加载当前话术的版本、节点和连线详情。
 *
 * @returns {Promise<void>} 返回详情加载完成后的 Promise。
 */
async function loadScriptDetails() {
  if (!activeScript.value) {
    versions.value = []
    activeVersion.value = null
    nodes.value = []
    edges.value = []
    return
  }

  versions.value = await fetchScriptVersionsApi(activeScript.value.id)
  if (!activeVersion.value || !versions.value.find((item) => item.id === activeVersion.value.id)) {
    activeVersion.value = versions.value[0] || null
  }

  if (!activeVersion.value) {
    nodes.value = []
    edges.value = []
    return
  }

  nodes.value = await fetchScriptNodesApi(activeVersion.value.id)
  edges.value = await fetchScriptEdgesApi(activeVersion.value.id)
  selectedNodeId.value = nodes.value[0]?.id || null
  selectedEdgeId.value = null
}

/**
 * 处理话术切换。
 *
 * @param {object} item 当前选中的话术对象。
 * @returns {Promise<void>} 返回切换完成后的 Promise。
 */
async function handleScriptSelect(item) {
  activeScript.value = item
  activeVersion.value = null
  clearEdgeDragState()
  await loadScriptDetails()
}

/**
 * 处理版本切换。
 *
 * @param {object} item 当前选中的版本对象。
 * @returns {Promise<void>} 返回切换完成后的 Promise。
 */
async function handleVersionSelect(item) {
  activeVersion.value = item
  clearEdgeDragState()
  nodes.value = await fetchScriptNodesApi(item.id)
  edges.value = await fetchScriptEdgesApi(item.id)
  selectedNodeId.value = nodes.value[0]?.id || null
  selectedEdgeId.value = null
}

/**
 * 打开新增话术弹窗。
 *
 * @returns {void}
 */
function openCreateScriptDialog() {
  scriptDialogMode.value = 'create'
  editingScriptId.value = null
  Object.assign(scriptForm, createDefaultScriptForm())
  scriptDialogVisible.value = true
}

/**
 * 打开编辑话术模板弹窗。
 *
 * @param {object} item 当前要编辑的话术模板对象。
 * @returns {void}
 */
function openEditScriptDialog(item) {
  scriptDialogMode.value = 'edit'
  editingScriptId.value = item.id
  Object.assign(scriptForm, {
    script_name: item.script_name,
    business_type: item.business_type || '',
    description: item.description || '',
    script_status: item.script_status,
  })
  scriptDialogVisible.value = true
}

/**
 * 生成系统内部使用的话术模板编码。
 *
 * @returns {string} 返回自动生成的话术模板编码。
 */
function buildAutoScriptCode() {
  return `script_${Date.now()}`
}

/**
 * 校验话术模板表单。
 *
 * @returns {boolean} 校验通过返回 `true`，否则返回 `false`。
 */
function validateScriptForm() {
  if (!scriptForm.script_name.trim()) {
    ElMessage.warning('请输入话术模板名称')
    return false
  }
  return true
}

/**
 * 提交话术主档。
 *
 * @returns {Promise<void>} 返回保存完成后的 Promise。
 */
async function submitScript() {
  if (!validateScriptForm()) {
    return
  }
  submittingScript.value = true
  try {
    if (scriptDialogMode.value === 'create') {
      await createScriptApi({
        ...scriptForm,
        script_code: buildAutoScriptCode(),
      })
      ElMessage.success('话术模板已创建')
    } else {
      await updateScriptApi(editingScriptId.value, {
        script_name: scriptForm.script_name,
        business_type: scriptForm.business_type || null,
        description: scriptForm.description || null,
        script_status: scriptForm.script_status,
      })
      ElMessage.success('话术模板已更新')
    }
    scriptDialogVisible.value = false
    await loadScripts()
  } finally {
    submittingScript.value = false
  }
}

/**
 * 删除指定话术模板。
 *
 * @param {object} item 当前要删除的话术模板对象。
 * @returns {Promise<void>} 返回删除完成后的 Promise。
 */
async function removeScript(item) {
  await ElMessageBox.confirm(`确定删除话术模板「${item.script_name}」吗？`, '删除确认', { type: 'warning' })
  await deleteScriptApi(item.id)
  ElMessage.success('话术模板已删除')
  if (activeScript.value?.id === item.id) {
    activeScript.value = null
    activeVersion.value = null
    nodes.value = []
    edges.value = []
  }
  await loadScripts()
}

/**
 * 导入系统内置的名酒品鉴会邀约示例，并自动切换到该示例进行查看。
 *
 * @returns {Promise<void>} 返回示例导入完成后的 Promise。
 */
async function importWineTastingDemo() {
  await ElMessageBox.confirm('系统会为当前账号导入一套“名酒品鉴会邀约”示例话术；如果已存在旧版同类示例，会先自动重建，是否继续？', '导入系统示例', {
    type: 'info',
  })
  const createdScript = await createWineTastingDemoApi()
  ElMessage.success('系统示例已导入')
  await loadScripts()
  const matchedScript = scripts.value.find((item) => item.id === createdScript.id)
  if (matchedScript) {
    await handleScriptSelect(matchedScript)
  }
}

/**
 * 导入系统内置的少儿编程教育推广示例，并自动切换到该示例进行查看。
 *
 * @returns {Promise<void>} 返回示例导入完成后的 Promise。
 */
async function importKidsCodingDemo() {
  await ElMessageBox.confirm('系统会为当前账号导入一套“少儿编程教育推广”示例话术；如果已存在旧版同类示例，会先自动重建，是否继续？', '导入系统示例', {
    type: 'info',
  })
  const createdScript = await createKidsCodingDemoApi()
  ElMessage.success('少儿编程示例已导入')
  await loadScripts()
  const matchedScript = scripts.value.find((item) => item.id === createdScript.id)
  if (matchedScript) {
    await handleScriptSelect(matchedScript)
  }
}

/**
 * 打开新增版本弹窗。
 *
 * @returns {void}
 */
function openCreateVersionDialog() {
  Object.assign(versionForm, createDefaultVersionForm(), {
    version_no: versions.value.length ? Math.max(...versions.value.map((item) => item.version_no)) + 1 : 1,
    version_label: `${activeScript.value?.script_name || '流程'} V${versions.value.length + 1}`,
  })
  versionDialogVisible.value = true
}

/**
 * 提交版本创建。
 *
 * @returns {Promise<void>} 返回版本创建完成后的 Promise。
 */
async function submitVersion() {
  if (!activeScript.value) {
    ElMessage.warning('请先选择话术')
    return
  }
  if (!versionForm.version_label.trim()) {
    ElMessage.warning('请输入流程版本名称')
    return
  }

  submittingVersion.value = true
  try {
    const createdVersion = await createScriptVersionApi(activeScript.value.id, {
      version_no: versionForm.version_no,
      version_label: versionForm.version_label,
      start_node_code: null,
      canvas_json: {
        custom_variables: customVariables.value,
      },
      remark: versionForm.remark || null,
    })
    versionDialogVisible.value = false
    ElMessage.success('流程版本已创建')
    await loadScriptDetails()
    const matchedVersion = versions.value.find((item) => item.id === createdVersion.id)
    if (matchedVersion) {
      await handleVersionSelect(matchedVersion)
    }
  } finally {
    submittingVersion.value = false
  }
}

/**
 * 删除指定流程版本，并在删除后自动切换到剩余版本。
 *
 * @param {object} item 当前要删除的版本对象。
 * @returns {Promise<void>} 返回删除完成后的 Promise。
 */
async function removeVersion(item) {
  if (!activeScript.value) {
    return
  }
  const currentScriptId = activeScript.value.id
  await ElMessageBox.confirm(`确定删除流程版本「${item.version_label}」吗？`, '删除确认', { type: 'warning' })
  await deleteScriptVersionApi(currentScriptId, item.id)
  ElMessage.success('流程版本已删除')
  if (activeVersion.value?.id === item.id) {
    activeVersion.value = null
  }
  await loadScripts()
  const currentScript = scripts.value.find((scriptItem) => scriptItem.id === currentScriptId) || null
  if (currentScript) {
    await handleScriptSelect(currentScript)
  }
}

/**
 * 发布指定版本。
 *
 * @param {object} item 当前要发布的版本对象。
 * @returns {Promise<void>} 返回发布完成后的 Promise。
 */
async function publishVersion(item) {
  if (!activeScript.value) {
    return
  }
  await publishScriptVersionApi(activeScript.value.id, item.id)
  ElMessage.success('版本已发布')
  await loadScripts()
  await loadScriptDetails()
}

/**
 * 根据节点模板打开新增节点弹窗。
 *
 * @param {object} templateItem 节点模板对象。
 * @returns {void}
 */
function openCreateNodeDialog(templateItem) {
  nodeDialogMode.value = 'create'
  editingNodeId.value = null
  const defaultNode = {
    node_code: buildNodeCode(templateItem.type),
    node_name: templateItem.label,
    node_type: templateItem.type,
  }
  Object.assign(nodeForm, createDefaultNodeForm(), buildNodeFormFromNode({ ...defaultNode, node_config: buildDefaultNodeConfig(templateItem.type) }))
  pendingNodePosition.value = computeNewNodePosition()
  nodeDialogVisible.value = true
}

/**
 * 打开编辑节点弹窗。
 *
 * @param {object} node 当前选中的节点对象。
 * @returns {void}
 */
function openEditNodeDialog(node) {
  nodeDialogMode.value = 'edit'
  editingNodeId.value = node.id
  selectedNodeId.value = node.id
  Object.assign(nodeForm, createDefaultNodeForm(), buildNodeFormFromNode(node))
  nodeDialogVisible.value = true
}

/**
 * 在节点类型变更时同步刷新该类型对应的默认配置。
 *
 * @returns {void}
 */
function handleNodeTypeChange() {
  const defaultConfig = buildNodeFormFromNode({
    node_code: nodeForm.node_code,
    node_name: nodeForm.node_name,
    node_type: nodeForm.node_type,
    node_config: buildDefaultNodeConfig(nodeForm.node_type),
    audio_asset_id: nodeForm.audio_asset_id,
  })
  Object.assign(nodeForm, {
    ...defaultConfig,
    node_code: nodeForm.node_code,
    node_name: nodeForm.node_name,
  })
}

/**
 * 保存节点。
 *
 * @returns {Promise<void>} 返回保存完成后的 Promise。
 */
async function submitNode() {
  if (!activeVersion.value) {
    ElMessage.warning('请先选择版本')
    return
  }
  if (!nodeForm.node_name.trim()) {
    ElMessage.warning('请输入节点名称')
    return
  }
  const duplicateNodeName = nodes.value.find((item) => {
    if (nodeDialogMode.value === 'edit' && item.id === editingNodeId.value) {
      return false
    }
    return item.node_name.trim() === nodeForm.node_name.trim()
  })
  if (duplicateNodeName) {
    ElMessage.warning('节点名称重复，请修改后再保存')
    return
  }
  if (nodeForm.node_type === 'asr') {
    if (!nodeForm.asr_branch_items.length) {
      ElMessage.warning('请至少配置一个识别分支')
      return
    }
    const branchNameSet = new Set()
    for (const branchItem of nodeForm.asr_branch_items) {
      const normalizedBranchName = branchItem.branch_name.trim()
      if (!normalizedBranchName) {
        ElMessage.warning(`请为 ${branchItem.route_code} 分支填写分支名称`)
        return
      }
      if (branchNameSet.has(normalizedBranchName)) {
        ElMessage.warning(`识别分支名称“${normalizedBranchName}”重复，请修改后再保存`)
        return
      }
      branchNameSet.add(normalizedBranchName)
    }
    const invalidBranch = nodeForm.asr_branch_items.find((item) => !splitInputTokens(item.keywords_text).length)
    if (invalidBranch) {
      ElMessage.warning(`请为 ${invalidBranch.route_code} 分支填写关键词`)
      return
    }
  }
  if (isPlaybackNodeType(nodeForm.node_type) && !nodeForm.prompt_text.trim()) {
    ElMessage.warning('请输入播报文案')
    return
  }
  if (nodeForm.playback_source === 'local' && isPlaybackNodeType(nodeForm.node_type) && !nodeForm.audio_asset_id) {
    ElMessage.warning('请选择本地录音，或者先生成一条本地录音')
    return
  }

  submittingNode.value = true
  try {
    if (nodeDialogMode.value === 'create') {
      const createdNode = await createScriptNodeApi(activeVersion.value.id, {
        node_code: nodeForm.node_code,
        node_name: nodeForm.node_name,
        node_type: nodeForm.node_type,
        position_x: pendingNodePosition.value.x,
        position_y: pendingNodePosition.value.y,
        audio_asset_id: nodeForm.playback_source === 'local' ? nodeForm.audio_asset_id || null : null,
        node_config: buildNodeConfigFromForm(),
      })
      nodes.value.push(createdNode)
      selectedNodeId.value = createdNode.id
      ElMessage.success('节点已创建')
    } else {
      const currentNode = nodes.value.find((item) => item.id === editingNodeId.value)
      if (!currentNode) {
        return
      }
      const updatedNode = await updateScriptNodeApi(editingNodeId.value, {
        node_name: nodeForm.node_name,
        node_type: nodeForm.node_type,
        position_x: currentNode.position_x,
        position_y: currentNode.position_y,
        audio_asset_id: nodeForm.playback_source === 'local' ? nodeForm.audio_asset_id || null : null,
        node_config: buildNodeConfigFromForm(),
      })
      replaceNode(updatedNode)
      ElMessage.success('节点已更新')
    }
    nodeDialogVisible.value = false
  } finally {
    submittingNode.value = false
  }
}

/**
 * 为识别节点新增下一个可用字母分支。
 *
 * @returns {void}
 */
function addAsrBranch() {
  const usedRouteCodes = new Set(nodeForm.asr_branch_items.map((item) => item.route_code))
  const nextRouteCode = routeCodeOptions.find((item) => !usedRouteCodes.has(item))
  if (!nextRouteCode) {
    ElMessage.warning('识别分支最多支持 A 到 Z 共 26 个分支')
    return
  }
  nodeForm.asr_branch_items.push({
    route_code: nextRouteCode,
    branch_name: `${nextRouteCode}分支`,
    keywords_text: '',
  })
}

/**
 * 从识别节点中移除指定字母分支。
 *
 * @param {string} routeCode 需要删除的分支代号。
 * @returns {void}
 */
function removeAsrBranch(routeCode) {
  if (nodeForm.asr_branch_items.length <= 1) {
    ElMessage.warning('识别节点至少保留一个分支')
    return
  }
  nodeForm.asr_branch_items = nodeForm.asr_branch_items.filter((item) => item.route_code !== routeCode)
}

/**
 * 打开编辑连线弹窗。
 *
 * @param {object} edge 当前选中的连线对象。
 * @returns {void}
 */
function openEditEdgeDialog(edge) {
  const sourceNode = nodes.value.find((item) => item.node_code === edge.from_node_code)
  edgeDialogMode.value = 'edit'
  editingEdgeId.value = edge.id
  Object.assign(edgeForm, {
    edge_code: edge.edge_code,
    from_node_code: edge.from_node_code,
    to_node_code: edge.to_node_code,
    condition_type: edge.condition_type,
    condition_config_text: formatJson(edge.condition_config),
    route_code: inferRecognizeRouteCode(sourceNode, edge),
    sort_order: edge.sort_order,
  })
  edgeDialogVisible.value = true
}

/**
 * 根据两个节点打开新增连线弹窗。
 *
 * @param {object} sourceNode 起始节点对象。
 * @param {object} targetNode 目标节点对象。
 * @returns {void}
 */
function openCreateEdgeDialog(sourceNode, targetNode) {
  edgeDialogMode.value = 'create'
  editingEdgeId.value = null
  const recognizeRoute = inferDefaultRecognizeRoute(sourceNode)
  if (sourceNode.node_type === 'asr' && !recognizeRoute) {
    ElMessage.warning('当前识别节点的分支连线都已使用，请先删除旧连线或新增分支')
    clearEdgeDragState()
    return
  }
  Object.assign(edgeForm, {
    edge_code: buildEdgeCode(),
    from_node_code: sourceNode.node_code,
    to_node_code: targetNode.node_code,
    condition_type: sourceNode.node_type === 'asr' ? 'keyword' : 'always',
    condition_config_text: '{}',
    route_code: recognizeRoute || 'DEFAULT',
    sort_order: edges.value.length + 1,
  })
  edgeDialogVisible.value = true
}

/**
 * 关闭连线弹窗并重置临时连线状态。
 *
 * @returns {void}
 */
function closeEdgeDialog() {
  edgeDialogVisible.value = false
  clearEdgeDragState()
}

/**
 * 根据识别分支节点当前已存在的出线，推断新建连线时的默认分支代号。
 *
 * @param {object} sourceNode 起始节点对象。
 * @returns {string | null} 返回建议的分支代号；全部占用时返回 `null`。
 */
function inferDefaultRecognizeRoute(sourceNode) {
  if (!sourceNode || sourceNode.node_type !== 'asr') {
    return 'A'
  }
  const configuredRoutes = resolveRecognizeBranches(sourceNode).map((item) => item.route_code)
  const usedRoutes = edges.value
    .filter((item) => item.from_node_code === sourceNode.node_code)
    .map((item) => inferRecognizeRouteCode(sourceNode, item))
  const nextRouteCode = configuredRoutes.find((item) => !usedRoutes.includes(item))
  if (nextRouteCode) {
    return nextRouteCode
  }
  if (!usedRoutes.includes('DEFAULT')) {
    return 'DEFAULT'
  }
  return null
}

/**
 * 根据识别分支节点和连线配置推断当前连线属于哪个字母分支或兜底分支。
 *
 * @param {object | null} sourceNode 起始节点对象，可为空。
 * @param {object} edge 当前连线对象。
 * @returns {string} 返回分支代号，例如 `A`、`D`、`DEFAULT`。
 */
function inferRecognizeRouteCode(sourceNode, edge) {
  if (!sourceNode || sourceNode.node_type !== 'asr') {
    return 'A'
  }
  const routeCode = edge.condition_config?.route_code
  if (routeCode) {
    return routeCode
  }
  if (edge.condition_type === 'nomatch') {
    return 'DEFAULT'
  }
  const branches = resolveRecognizeBranches(sourceNode)
  const edgeKeywords = edge.condition_config?.keywords || []
  for (const branchItem of branches) {
    if (arrayEquals(branchItem.keywords, edgeKeywords)) {
      return branchItem.route_code
    }
  }
  return 'A'
}

/**
 * 将当前连线表单转换为后端保存所需的条件类型和配置。
 *
 * @param {object | null} sourceNode 起始节点对象，可为空。
 * @returns {{condition_type: string, condition_config: object}} 返回可提交的连线条件对象。
 */
function buildEdgePayloadForSubmit(sourceNode) {
  if (!sourceNode || sourceNode.node_type !== 'asr') {
    return {
      condition_type: edgeForm.condition_type,
      condition_config: parseJsonText(edgeForm.condition_config_text, {}),
    }
  }
  return buildRecognizeEdgePayload(sourceNode, edgeForm.route_code)
}

/**
 * 根据识别节点和分支代号生成实际连线条件。
 *
 * @param {object} sourceNode 起始识别节点对象。
 * @param {string} routeCode 当前分支代号。
 * @returns {{condition_type: string, condition_config: object}} 返回连线条件对象。
 */
function buildRecognizeEdgePayload(sourceNode, routeCode) {
  const branchItem = resolveRecognizeBranches(sourceNode).find((item) => item.route_code === routeCode)
  if (branchItem) {
    return {
      condition_type: 'keyword',
      condition_config: {
        route_code: branchItem.route_code,
        branch_name: branchItem.branch_name,
        keywords: branchItem.keywords,
      },
    }
  }
  return {
    condition_type: 'nomatch',
    condition_config: {
      route_code: 'DEFAULT',
      label: resolveAsrDefaultBranchText(sourceNode.node_config || {}),
    },
  }
}

/**
 * 提交连线。
 *
 * @returns {Promise<void>} 返回保存完成后的 Promise。
 */
async function submitEdge() {
  if (!activeVersion.value) {
    return
  }
  if (!edgeForm.to_node_code || edgeForm.to_node_code === edgeForm.from_node_code) {
    ElMessage.warning('请选择有效的目标节点')
    return
  }

  submittingEdge.value = true
  try {
    const sourceNode = nodes.value.find((item) => item.node_code === edgeForm.from_node_code) || null
    if (sourceNode?.node_type === 'asr') {
      const duplicateEdge = edges.value.find((item) => {
        if (edgeDialogMode.value === 'edit' && item.id === editingEdgeId.value) {
          return false
        }
        return item.from_node_code === edgeForm.from_node_code && inferRecognizeRouteCode(sourceNode, item) === edgeForm.route_code
      })
      if (duplicateEdge) {
        ElMessage.warning(`${resolveRecognizeRouteLabelByCode(edgeForm.route_code, sourceNode)} 已经绑定到其他连线，请重新选择`)
        return
      }
    }
    const normalizedEdgePayload = buildEdgePayloadForSubmit(sourceNode)
    if (edgeDialogMode.value === 'create') {
      const createdEdge = await createScriptEdgeApi(activeVersion.value.id, {
        edge_code: edgeForm.edge_code,
        from_node_code: edgeForm.from_node_code,
        to_node_code: edgeForm.to_node_code,
        condition_type: normalizedEdgePayload.condition_type,
        condition_config: normalizedEdgePayload.condition_config,
        sort_order: edgeForm.sort_order,
      })
      edges.value.push(createdEdge)
      selectedEdgeId.value = createdEdge.id
      ElMessage.success('连线已创建')
    } else {
      const updatedEdge = await updateScriptEdgeApi(editingEdgeId.value, {
        from_node_code: edgeForm.from_node_code,
        to_node_code: edgeForm.to_node_code,
        condition_type: normalizedEdgePayload.condition_type,
        condition_config: normalizedEdgePayload.condition_config,
        sort_order: edgeForm.sort_order,
      })
      replaceEdge(updatedEdge)
      ElMessage.success('连线已更新')
    }
    edgeDialogVisible.value = false
    clearEdgeDragState()
  } finally {
    submittingEdge.value = false
  }
}

/**
 * 保存当前画布布局与起始节点配置。
 *
 * @returns {Promise<void>} 返回保存完成后的 Promise。
 */
async function saveCanvasLayout() {
  if (!activeVersion.value) {
    return
  }
  const startNode = nodes.value.find((item) => item.node_type === 'start') || selectedNode.value || nodes.value[0]
  const updatedVersion = await updateScriptVersionApi(activeVersion.value.id, {
    start_node_code: startNode?.node_code || null,
    canvas_json: {
      node_count: nodes.value.length,
      edge_count: edges.value.length,
      updated_at: new Date().toISOString(),
      custom_variables: customVariables.value,
    },
    remark: activeVersion.value.remark,
  })
  activeVersion.value = updatedVersion
  ElMessage.success('画布布局已保存')
}

/**
 * 将指定节点设置为起始节点并立即保存。
 *
 * @param {object} node 需要设置为起始节点的节点对象。
 * @returns {Promise<void>} 返回保存完成后的 Promise。
 */
async function setStartNode(node) {
  if (!activeVersion.value) {
    return
  }
  activeVersion.value = await updateScriptVersionApi(activeVersion.value.id, {
    start_node_code: node.node_code,
    canvas_json: {
      ...(activeVersion.value.canvas_json || {}),
      custom_variables: customVariables.value,
    },
    remark: activeVersion.value.remark,
  })
  ElMessage.success('起始节点已更新')
}

/**
 * 打开新增自定义变量弹窗。
 *
 * @returns {void}
 */
function openVariableDialog() {
  Object.assign(variableForm, createDefaultVariableForm())
  variableDialogVisible.value = true
}

/**
 * 生成变量占位符文本。
 *
 * @param {string} variableKey 变量键名。
 * @returns {string} 返回可插入文案中的变量占位符。
 */
function buildVariableToken(variableKey) {
  return `{{${variableKey}}}`
}

/**
 * 将变量快捷插入到当前节点配置中。
 *
 * @param {{key: string}} variableItem 当前要插入的变量对象。
 * @returns {void}
 */
function insertVariableIntoNode(variableItem) {
  const promptText = String(nodeForm.prompt_text || '')
  nodeForm.prompt_text = `${promptText}${promptText ? ' ' : ''}${buildVariableToken(variableItem.key)}`
  ElMessage.success(`已插入变量 ${buildVariableToken(variableItem.key)}`)
}

/**
 * 根据当前播报文案生成一条本地录音库记录，方便后续复用。
 *
 * @returns {Promise<void>} 返回本地录音记录创建完成后的 Promise。
 */
async function generateLocalAudioAssetFromPrompt() {
  if (!nodeForm.prompt_text.trim()) {
    ElMessage.warning('请先输入播报文案')
    return
  }
  const createdAsset = await generateTtsAudioAssetApi({
    asset_name: `${nodeForm.node_name || resolveNodeLabel(nodeForm.node_type)}录音`,
    prompt_text: nodeForm.prompt_text.trim(),
    tts_provider_id: nodeForm.tts_provider_id || null,
    tts_voice_profile: nodeForm.tts_voice_profile || null,
    channels: 1,
  })
  nodeForm.audio_asset_id = createdAsset.id
  await loadAudioAssets()
  ElMessage.success('已真实生成本地录音，并绑定到当前节点')
}

/**
 * 保存自定义变量到当前流程版本。
 *
 * @returns {Promise<void>} 返回保存完成后的 Promise。
 */
async function submitVariable() {
  if (!activeVersion.value) {
    ElMessage.warning('请先选择流程版本')
    return
  }
  if (!variableForm.label.trim() || !variableForm.key.trim()) {
    ElMessage.warning('请输入完整的变量名称和键名')
    return
  }
  const nextVariables = [
    ...customVariables.value.filter((item) => item.key !== variableForm.key.trim()),
    {
      key: variableForm.key.trim(),
      label: variableForm.label.trim(),
      example: variableForm.example.trim(),
    },
  ]
  activeVersion.value = await updateScriptVersionApi(activeVersion.value.id, {
    start_node_code: activeVersion.value.start_node_code,
    canvas_json: {
      ...(activeVersion.value.canvas_json || {}),
      custom_variables: nextVariables,
    },
    remark: activeVersion.value.remark,
  })
  variableDialogVisible.value = false
  ElMessage.success('自定义变量已保存')
}

/**
 * 选中指定节点。
 *
 * @param {object} node 当前点击的节点对象。
 * @returns {void}
 */
function selectNode(node) {
  selectedNodeId.value = node.id
  selectedEdgeId.value = null
}

/**
 * 选中指定连线。
 *
 * @param {object} edge 当前选中的连线对象。
 * @returns {void}
 */
function selectEdge(edge) {
  selectedEdgeId.value = edge.id
  selectedNodeId.value = null
}

/**
 * 开始拖拽节点。
 *
 * @param {MouseEvent} event 鼠标按下事件对象。
 * @param {object} node 当前拖拽的节点对象。
 * @returns {void}
 */
function startNodeDrag(event, node) {
  clearPanState()
  if (dragLinkState.active) {
    return
  }
  if (event.target instanceof HTMLElement && event.target.closest('.node-handle')) {
    return
  }
  const boardElement = boardRef.value
  if (!boardElement) {
    return
  }
  const boardRect = boardElement.getBoundingClientRect()
  dragState.active = true
  dragState.nodeId = node.id
  dragState.offsetX = (event.clientX - boardRect.left + boardElement.scrollLeft) / canvasScale.value - node.position_x
  dragState.offsetY = (event.clientY - boardRect.top + boardElement.scrollTop) / canvasScale.value - node.position_y
  selectedNodeId.value = node.id
}

/**
 * 在窗口鼠标移动时同步拖拽节点位置。
 *
 * @param {MouseEvent} event 鼠标移动事件对象。
 * @returns {void}
 */
function handleWindowMouseMove(event) {
  if (sidebarResizeState.active) {
    const nextWidth = sidebarResizeState.startWidth + event.clientX - sidebarResizeState.startClientX
    sidebarWidth.value = Math.min(520, Math.max(280, nextWidth))
  }
  if (!boardRef.value) {
    return
  }
  if (panState.active) {
    boardRef.value.scrollLeft = panState.startScrollLeft - (event.clientX - panState.startClientX)
    boardRef.value.scrollTop = panState.startScrollTop - (event.clientY - panState.startClientY)
  }
  const boardRect = boardRef.value.getBoundingClientRect()
  if (dragLinkState.active) {
    dragLinkState.currentX = (event.clientX - boardRect.left + boardRef.value.scrollLeft) / canvasScale.value
    dragLinkState.currentY = (event.clientY - boardRect.top + boardRef.value.scrollTop) / canvasScale.value
  }
  if (!dragState.active) {
    return
  }
  const targetNode = nodes.value.find((item) => item.id === dragState.nodeId)
  if (!targetNode) {
    return
  }
  targetNode.position_x = Math.max(
    20,
    (event.clientX - boardRect.left + boardRef.value.scrollLeft) / canvasScale.value - dragState.offsetX,
  )
  targetNode.position_y = Math.max(
    20,
    (event.clientY - boardRect.top + boardRef.value.scrollTop) / canvasScale.value - dragState.offsetY,
  )
}

/**
 * 在窗口鼠标松开时结束拖拽并持久化节点位置。
 *
 * @returns {Promise<void>} 返回持久化完成后的 Promise。
 */
async function handleWindowMouseUp() {
  if (sidebarResizeState.active) {
    clearSidebarResizeState()
  }
  if (panState.active) {
    clearPanState()
  }
  if (dragLinkState.active) {
    clearEdgeDragState()
  }
  if (!dragState.active) {
    return
  }
  const targetNode = nodes.value.find((item) => item.id === dragState.nodeId)
  dragState.active = false
  dragState.nodeId = null
  if (!targetNode) {
    return
  }
  const updatedNode = await updateScriptNodeApi(targetNode.id, {
    node_name: targetNode.node_name,
    node_type: targetNode.node_type,
    position_x: targetNode.position_x,
    position_y: targetNode.position_y,
    audio_asset_id: targetNode.audio_asset_id,
    node_config: targetNode.node_config,
  })
  replaceNode(updatedNode)
}

/**
 * 从节点右侧锚点开始拖拽连线。
 *
 * @param {MouseEvent} event 鼠标按下事件对象。
 * @param {object} node 当前作为起点的节点对象。
 * @returns {void}
 */
function startEdgeDrag(event, node) {
  clearPanState()
  const boardElement = boardRef.value
  if (!boardElement) {
    return
  }
  const boardRect = boardElement.getBoundingClientRect()
  dragLinkState.active = true
  dragLinkState.sourceNodeId = node.id
  dragLinkState.currentX = (event.clientX - boardRect.left + boardElement.scrollLeft) / canvasScale.value
  dragLinkState.currentY = (event.clientY - boardRect.top + boardElement.scrollTop) / canvasScale.value
  selectedNodeId.value = node.id
  selectedEdgeId.value = null
}

/**
 * 将拖拽中的连线落到目标节点左侧锚点。
 *
 * @param {object} node 当前作为终点的节点对象。
 * @returns {void}
 */
function finishEdgeDrag(node) {
  const sourceNode = sourceDragNode.value
  if (!dragLinkState.active || !sourceNode) {
    clearDragState()
    return
  }
  if (sourceNode.id === node.id) {
    clearEdgeDragState()
    return
  }
  openCreateEdgeDialog(sourceNode, node)
}

/**
 * 在点击输入锚点时阻止节点拖拽，并确保仅处理连线吸附逻辑。
 *
 * @param {object} node 当前输入端所属的节点对象。
 * @returns {void}
 */
function prepareInputHandle(node) {
  void node
  clearPanState()
  clearDragState()
}

/**
 * 清理拖线状态。
 *
 * @returns {void}
 */
function clearEdgeDragState() {
  dragLinkState.active = false
  dragLinkState.sourceNodeId = null
  dragLinkState.currentX = 0
  dragLinkState.currentY = 0
}

/**
 * 清理节点拖拽状态，避免锚点点击后节点继续跟随鼠标。
 *
 * @returns {void}
 */
function clearDragState() {
  dragState.active = false
  dragState.nodeId = null
  dragState.offsetX = 0
  dragState.offsetY = 0
}

/**
 * 在按住画布空白区域时启动平移模式。
 *
 * @param {MouseEvent} event 鼠标按下事件对象。
 * @returns {void}
 */
function startBoardPan(event) {
  const boardElement = boardRef.value
  if (!boardElement) {
    return
  }
  if (!(event.target instanceof HTMLElement)) {
    return
  }
  if (
    event.target.closest('.flow-node') ||
    event.target.closest('.node-handle') ||
    event.target.closest('.flow-edge') ||
    event.target.closest('.edge-row')
  ) {
    return
  }
  clearDragState()
  clearEdgeDragState()
  panState.active = true
  panState.startClientX = event.clientX
  panState.startClientY = event.clientY
  panState.startScrollLeft = boardElement.scrollLeft
  panState.startScrollTop = boardElement.scrollTop
}

/**
 * 清理画布平移状态。
 *
 * @returns {void}
 */
function clearPanState() {
  panState.active = false
  panState.startClientX = 0
  panState.startClientY = 0
  panState.startScrollLeft = 0
  panState.startScrollTop = 0
}

/**
 * 切换左侧面板的展开与收起状态。
 *
 * @returns {void}
 */
function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

/**
 * 开始拖动左侧面板宽度。
 *
 * @param {MouseEvent} event 鼠标按下事件对象。
 * @returns {void}
 */
function startSidebarResize(event) {
  sidebarCollapsed.value = false
  sidebarResizeState.active = true
  sidebarResizeState.startClientX = event.clientX
  sidebarResizeState.startWidth = sidebarWidth.value
}

/**
 * 清理左侧面板拖拽状态。
 *
 * @returns {void}
 */
function clearSidebarResizeState() {
  sidebarResizeState.active = false
  sidebarResizeState.startClientX = 0
  sidebarResizeState.startWidth = sidebarWidth.value
}

/**
 * 删除指定节点及其相关连线。
 *
 * @param {object} node 当前要删除的节点对象。
 * @returns {Promise<void>} 返回删除完成后的 Promise。
 */
async function removeNode(node) {
  await ElMessageBox.confirm(`确定删除节点「${node.node_name}」吗？`, '删除确认', { type: 'warning' })
  const relatedEdges = edges.value.filter(
    (item) => item.from_node_code === node.node_code || item.to_node_code === node.node_code,
  )
  for (const edge of relatedEdges) {
    await deleteScriptEdgeApi(edge.id)
  }
  await deleteScriptNodeApi(node.id)
  edges.value = edges.value.filter((item) => !relatedEdges.find((edge) => edge.id === item.id))
  nodes.value = nodes.value.filter((item) => item.id !== node.id)
  selectedNodeId.value = null
  ElMessage.success('节点已删除')
}

/**
 * 删除指定连线。
 *
 * @param {object} edge 当前要删除的连线对象。
 * @returns {Promise<void>} 返回删除完成后的 Promise。
 */
async function removeEdge(edge) {
  await deleteScriptEdgeApi(edge.id)
  edges.value = edges.value.filter((item) => item.id !== edge.id)
  selectedEdgeId.value = null
  ElMessage.success('连线已删除')
}

/**
 * 弹出确认框后删除指定连线，避免误删当前流程关系。
 *
 * @param {object} edge 当前要删除的连线对象。
 * @returns {Promise<void>} 返回删除完成后的 Promise。
 */
async function confirmRemoveEdge(edge) {
  await ElMessageBox.confirm('确定删除这条连线吗？删除后可以重新连接到正确的播报节点。', '删除确认', { type: 'warning' })
  await removeEdge(edge)
}

/**
 * 根据节点类型生成默认配置对象。
 *
 * @param {string} nodeType 节点类型值。
 * @returns {object} 返回默认节点配置对象。
 */
function buildDefaultNodeConfig(nodeType) {
  if (nodeType === 'start') {
    return { prompt: '您好，我是智能外呼助理。', playback_source: 'tts', next_step: '请听候客户反馈。' }
  }
  if (nodeType === 'playback') {
    return { prompt: '这里填写播报文案', playback_source: 'tts', use_tts: true }
  }
  if (nodeType === 'asr') {
    return {
      asr_branches: [
        { route_code: 'A', branch_name: '正向意向', keywords: ['是', '好', '可以啊', '好的'] },
        { route_code: 'B', branch_name: '拒绝/异议', keywords: ['不要', '挂机', '不需要'] },
      ],
      default_branch_label: '未识别/超时/静音',
      timeout_seconds: 5,
    }
  }
  return { prompt: '流程结束，感谢接听。', playback_source: 'tts' }
}

/**
 * 计算新节点默认落点位置。
 *
 * @returns {{x: number, y: number}} 返回新节点建议坐标。
 */
function computeNewNodePosition() {
  const index = nodes.value.length
  return {
    x: 80 + (index % 3) * 260,
    y: 80 + Math.floor(index / 3) * 180,
  }
}

/**
 * 根据节点类型生成新的节点编码。
 *
 * @param {string} nodeType 节点类型值。
 * @returns {string} 返回尽量可读且唯一的节点编码。
 */
function buildNodeCode(nodeType) {
  const baseCode = nodeType.replace(/[^a-z0-9_]/gi, '_').toLowerCase()
  return `${baseCode}_${generateCompactUuid()}`
}

/**
 * 生成用于连线编码的唯一字符串，避免因节点编码过长导致参数校验失败。
 *
 * @returns {string} 返回长度受控的连线编码字符串。
 */
function buildEdgeCode() {
  return `edge_${generateCompactUuid()}`
}

/**
 * 生成 32 位紧凑 UUID 字符串，用于节点编码避免重复冲突。
 *
 * @returns {string} 返回去掉连字符后的 32 位 UUID 字符串。
 */
function generateCompactUuid() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID().replace(/-/g, '')
  }
  return `${Date.now().toString(16)}${Math.random().toString(16).slice(2, 18)}`.slice(0, 32).padEnd(32, '0')
}

/**
 * 将更新后的节点替换到当前节点列表中。
 *
 * @param {object} updatedNode 后端返回的最新节点对象。
 * @returns {void}
 */
function replaceNode(updatedNode) {
  const targetIndex = nodes.value.findIndex((item) => item.id === updatedNode.id)
  if (targetIndex >= 0) {
    nodes.value[targetIndex] = updatedNode
  }
}

/**
 * 将更新后的连线替换到当前连线列表中。
 *
 * @param {object} updatedEdge 后端返回的最新连线对象。
 * @returns {void}
 */
function replaceEdge(updatedEdge) {
  const targetIndex = edges.value.findIndex((item) => item.id === updatedEdge.id)
  if (targetIndex >= 0) {
    edges.value[targetIndex] = updatedEdge
  }
}

/**
 * 根据节点类型返回中文展示名称。
 *
 * @param {string} nodeType 节点类型值。
 * @returns {string} 返回节点类型中文文本。
 */
function resolveNodeLabel(nodeType) {
  return nodeTemplates.find((item) => item.type === nodeType)?.label || nodeType
}

/**
 * 根据节点编码解析节点名称，供连线详情和编辑表单展示。
 *
 * @param {string} nodeCode 当前节点编码。
 * @returns {string} 返回节点名称，找不到时回退为节点编码。
 */
function resolveNodeNameByCode(nodeCode) {
  const matchedNode = nodes.value.find((item) => item.node_code === nodeCode)
  return matchedNode?.node_name || nodeCode || '--'
}

/**
 * 将节点编码截断为适合卡片底部展示的短文本，避免撑出节点边框。
 *
 * @param {string} nodeCode 原始节点编码。
 * @returns {string} 返回截断后的节点编码预览文本。
 */
function formatNodeCodePreview(nodeCode) {
  const normalizedCode = String(nodeCode || '')
  if (normalizedCode.length <= 10) {
    return normalizedCode
  }
  return `${normalizedCode.slice(0, 10)}...`
}

/**
 * 将连线对象转换为适合运营查看的中文说明。
 *
 * @param {object} edge 连线对象。
 * @returns {string} 返回可读的连线条件文本。
 */
function resolveEdgeLabel(edge) {
  const routeCode = edge.condition_config?.route_code
  if (routeCode) {
    if (routeCode === 'DEFAULT') {
      return `兜底：${edge.condition_config?.label || '未命中'}`
    }
    if (edge.condition_config?.branch_name) {
      return `${routeCode} 分支：${edge.condition_config.branch_name}`
    }
    return resolveRecognizeRouteLabelByCode(routeCode)
  }
  if (edge.condition_type === 'always') {
    return '默认流转'
  }
  return edge.condition_type
}

/**
 * 生成节点卡片内的预览文本。
 *
 * @param {object} node 节点对象。
 * @returns {string} 返回节点摘要文本。
 */
function resolveNodePreview(node) {
  const promptText = node.node_config?.prompt
  if (promptText) {
    const sourceText = node.node_config?.playback_source === 'local' ? '本地录音' : '在线生成'
    return `${sourceText}：${String(promptText)}`
  }
  if (node.node_type === 'asr') {
    const branchItems = normalizeAsrBranchItems(node.node_config || {})
    const branchPreview = branchItems
      .slice(0, 3)
      .map((item) => `${item.route_code}:${splitInputTokens(item.keywords_text).join(' / ') || '未配置'}`)
      .join(' | ')
    return `${branchPreview}${branchItems.length > 3 ? ` | 其余${branchItems.length - 3}个分支` : ''} | 兜底:${resolveAsrDefaultBranchText(node.node_config || {})}`
  }
  return '双击可编辑节点配置'
}

/**
 * 在组件挂载时初始化页面数据并注册拖拽监听。
 *
 * @returns {Promise<void>} 返回初始化完成后的 Promise。
 */
async function initializePage() {
  await Promise.all([loadScripts(), loadAudioAssets(), loadProviders()])
  window.addEventListener('mousemove', handleWindowMouseMove)
  window.addEventListener('mouseup', handleWindowMouseUp)
}

/**
 * 在组件卸载时注销全局拖拽监听。
 *
 * @returns {void}
 */
function destroyPage() {
  window.removeEventListener('mousemove', handleWindowMouseMove)
  window.removeEventListener('mouseup', handleWindowMouseUp)
}

onMounted(initializePage)
onBeforeUnmount(destroyPage)
</script>

<style scoped lang="scss">
.script-workbench {
  display: grid;
  gap: 20px;
  align-items: stretch;
}

.workbench-sidebar,
.flow-stage {
  min-height: calc(100vh - 150px);
}

.workbench-sidebar {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 22px;
  overflow: hidden auto;
}

.sidebar-topbar {
  display: flex;
  justify-content: flex-end;
}

.sidebar-resizer {
  width: 10px;
  cursor: col-resize;
  position: relative;
}

.sidebar-resizer::before {
  content: '';
  position: absolute;
  left: 4px;
  top: 24px;
  bottom: 24px;
  width: 2px;
  border-radius: 999px;
  background: linear-gradient(180deg, rgba(102, 147, 230, 0.2) 0%, rgba(102, 147, 230, 0.65) 50%, rgba(102, 147, 230, 0.2) 100%);
}

.sidebar-section {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.section-head h3 {
  margin: 0;
  font-size: 16px;
}

.section-head p {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--app-text-soft);
}

.script-card-list,
.version-card-list,
.palette-list,
.edge-list,
.variable-list,
.node-variable-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.script-card,
.version-card,
.palette-item,
.edge-row {
  width: 100%;
  border: 1px solid #d8e6ff;
  border-radius: 18px;
  background: linear-gradient(180deg, #fbfdff 0%, #eff5ff 100%);
  text-align: left;
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}

.script-card {
  padding: 14px 16px;
}

.script-card-main {
  width: 100%;
  border: none;
  background: transparent;
  text-align: left;
  padding: 0;
  cursor: pointer;
}

.script-card-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 10px;
}

.version-card {
  padding: 14px 16px;
}

.version-card-main {
  width: 100%;
  border: none;
  background: transparent;
  text-align: left;
  padding: 0;
  cursor: pointer;
}

.version-card-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 10px;
}

.script-card.is-active,
.version-card.is-active,
.edge-row.is-selected {
  border-color: #5390ff;
  box-shadow: 0 12px 26px rgba(46, 104, 215, 0.14);
  transform: translateY(-2px);
}

.script-card-head,
.version-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.script-card-meta,
.version-card small,
.version-card span {
  display: block;
  color: var(--app-text-soft);
  font-size: 12px;
  line-height: 1.6;
}

.palette-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 14px 16px;
  border-left: 4px solid var(--palette-color);
}

.palette-item span {
  font-size: 12px;
  color: var(--app-text-soft);
  line-height: 1.6;
}

.variable-list,
.node-variable-list {
  flex-direction: row;
  flex-wrap: wrap;
}

.variable-chip {
  display: inline-flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: 10px 12px;
  border: 1px solid #dce8ff;
  border-radius: 14px;
  background: #f9fbff;
  cursor: pointer;
}

.variable-chip strong {
  font-size: 12px;
  color: #38507f;
}

.variable-chip span {
  font-size: 11px;
  color: #6e7c9c;
}

.flow-stage {
  display: flex;
  flex-direction: column;
  padding: 24px;
  gap: 18px;
}

.sidebar-expand-button {
  margin-top: 10px;
}

.flow-topbar,
.flow-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.toolbar-info {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.info-pill {
  display: inline-flex;
  align-items: center;
  padding: 8px 12px;
  border-radius: 999px;
  background: #edf3ff;
  color: #2e62c7;
  font-size: 12px;
  font-weight: 700;
}

.info-pill.is-connecting {
  background: #fff0df;
  color: #b86900;
}

.board-hint {
  font-size: 12px;
  color: var(--app-text-soft);
}

.connection-guide {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  padding: 12px 16px;
  border-radius: 18px;
  background: linear-gradient(180deg, #f8fbff 0%, #eef5ff 100%);
  border: 1px solid #dbe8ff;
}

.guide-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #53627f;
}

.guide-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  box-shadow: 0 6px 12px rgba(34, 82, 183, 0.18);
}

.guide-dot.is-input {
  background: #4d86ff;
}

.guide-dot.is-output {
  background: #ff9955;
}

.zoom-label {
  font-size: 12px;
  color: var(--app-text-soft);
}

.flow-main {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 290px;
  gap: 16px;
  min-height: 0;
  flex: 1;
}

.flow-board {
  position: relative;
  height: 800px;
  overflow: auto;
  cursor: grab;
  border-radius: 28px;
  border: 1px solid #d5ead0;
  background:
    linear-gradient(180deg, rgba(240, 255, 234, 0.96) 0%, rgba(228, 247, 222, 0.92) 100%),
    radial-gradient(circle at top left, rgba(255, 255, 255, 0.65) 0%, rgba(255, 255, 255, 0) 34%);
}

.flow-board.is-panning {
  cursor: grabbing;
}

.flow-board::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(160, 206, 150, 0.16) 1px, transparent 1px),
    linear-gradient(90deg, rgba(160, 206, 150, 0.16) 1px, transparent 1px);
  background-size: 24px 24px;
  pointer-events: none;
}

.flow-board-stage-wrapper {
  position: relative;
}

.flow-board-stage {
  position: relative;
  width: 3200px;
  height: 3600px;
}

.flow-lines {
  position: absolute;
  inset: 0;
  width: 3200px;
  height: 3600px;
  pointer-events: none;
}

.flow-edge {
  fill: none;
  stroke: #5c8ff5;
  stroke-width: 3;
  stroke-linecap: round;
  stroke-linejoin: round;
  pointer-events: auto;
  cursor: pointer;
}

.flow-edge.is-selected {
  stroke: #ff8a55;
}

.flow-edge.is-preview {
  stroke: #ff9d58;
  stroke-dasharray: 8 6;
  opacity: 0.85;
}

.flow-edge-label-group {
  pointer-events: none;
}

.flow-edge-label-bg,
.flow-edge-label-text {
  pointer-events: auto;
}

.flow-edge-label-bg {
  fill: rgba(255, 255, 255, 0.92);
  stroke: #9ebcff;
  stroke-width: 1.5;
  filter: drop-shadow(0 6px 12px rgba(76, 112, 198, 0.14));
  cursor: pointer;
}

.flow-edge-label-bg.is-selected {
  fill: #fff2e8;
  stroke: #ff9a63;
}

.flow-edge-label-text {
  fill: #3c5ea8;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  user-select: none;
}

.flow-edge-label-text.is-selected {
  fill: #c46426;
}

.flow-node {
  position: absolute;
  width: 220px;
  border-radius: 18px;
  overflow: visible;
  background: #ffffff;
  box-shadow: 0 18px 34px rgba(88, 112, 159, 0.14);
  border: 1px solid rgba(180, 205, 255, 0.85);
  cursor: grab;
  user-select: none;
}

.flow-node.is-selected {
  box-shadow: 0 18px 36px rgba(74, 132, 255, 0.22);
}

.flow-node.is-connecting {
  outline: 3px solid rgba(255, 152, 78, 0.6);
}

.node-handle {
  position: absolute;
  top: 72px;
  width: 16px;
  height: 16px;
  border: 3px solid #ffffff;
  border-radius: 50%;
  background: #4d86ff;
  box-shadow: 0 8px 18px rgba(64, 110, 219, 0.24);
  cursor: crosshair;
  z-index: 2;
}

.node-handle.is-input {
  left: -8px;
}

.node-handle.is-output {
  right: -8px;
  background: #ff9955;
}

.dialog-hint {
  font-size: 12px;
  line-height: 1.8;
  color: #6e7c9c;
}

.node-form-stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}

.asr-branch-editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
}

.asr-branch-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  border: 1px solid #d8e6ff;
  border-radius: 16px;
  background: linear-gradient(180deg, #fbfdff 0%, #f2f7ff 100%);
}

.asr-branch-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.flow-node-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 11px 14px;
  color: #ffffff;
  font-size: 12px;
  font-weight: 700;
}

.flow-node.is-start .flow-node-head,
.flow-node.is-end .flow-node-head {
  background: linear-gradient(90deg, #7667ef 0%, #987af9 100%);
}

.flow-node.is-playback .flow-node-head {
  background: linear-gradient(90deg, #329bff 0%, #5bbcff 100%);
}

.flow-node.is-asr .flow-node-head {
  background: linear-gradient(90deg, #2cab9d 0%, #52c6b8 100%);
}

.flow-node.is-branch .flow-node-head {
  background: linear-gradient(90deg, #ff8f48 0%, #ffad67 100%);
}

.flow-node.is-intent .flow-node-head {
  background: linear-gradient(90deg, #f56d91 0%, #ff8eac 100%);
}

.flow-node.is-fallback .flow-node-head {
  background: linear-gradient(90deg, #72809a 0%, #8c9ab2 100%);
}

.node-delete {
  border: none;
  background: transparent;
  color: inherit;
  font-size: 16px;
  cursor: pointer;
}

.flow-node-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px;
}

.flow-node-body strong {
  color: #2f3f69;
}

.flow-node-body p {
  margin: 0;
  color: #6e7c9c;
  font-size: 12px;
  line-height: 1.7;
  min-height: 42px;
}

.flow-node-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px 14px;
  color: #6e7c9c;
  font-size: 11px;
}

.start-tag {
  padding: 3px 8px;
  border-radius: 999px;
  background: #e8f8ef;
  color: #16794c;
}

.flow-inspector {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.inspector-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 18px;
  border-radius: 22px;
  border: 1px solid #d9e6fb;
  background: linear-gradient(180deg, #fbfdff 0%, #f1f6ff 100%);
}

.inspector-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px;
  border-radius: 16px;
  background: #ffffff;
  border: 1px solid #dfebff;
  color: #55617f;
  font-size: 12px;
}

.inspector-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.edge-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 14px;
}

.edge-row span {
  font-size: 12px;
  color: var(--app-text-soft);
}

@media (max-width: 1400px) {
  .flow-main {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 1180px) {
  .script-workbench {
    grid-template-columns: 1fr !important;
  }

  .workbench-sidebar {
    width: auto !important;
  }

  .sidebar-resizer {
    display: none;
  }
}
</style>
